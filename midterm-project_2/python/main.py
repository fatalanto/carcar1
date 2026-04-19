import argparse
import logging
import os
import sys
import time
import csv
import re
import serial

# 官方預設的 import
from maze import Action, Maze
from score import ScoreboardServer, ScoreboardFake

# 設定日誌格式
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

# ================= 🌟 參數設定區 =================
TEAM_NAME = "MyTeam"  
SERVER_URL = "http://carcar.ntuee.org/scoreboard"
MAZE_FILE = r"C:\Users\88693\Desktop\大學\大一下\車車\bfs1\maze.csv" 
BT_PORT = "COM7"  # 請確保這是你裝置管理員看到的正確 COM 埠
BAUD_RATE = 9600
# ================================================

def load_graph(filename):
    """讀取地圖 CSV 並轉換成字典格式"""
    graph = {}
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node = int(row['index'])
                neighbors = {}
                # 處理可能存在的 float 字串 (如 "3.0")
                if row['North']: neighbors['N'] = int(float(row['North']))
                if row['East']:  neighbors['E'] = int(float(row['East']))
                if row['South']: neighbors['S'] = int(float(row['South']))
                if row['West']:  neighbors['W'] = int(float(row['West']))
                graph[node] = neighbors
        return graph
    except Exception as e:
        log.error(f"❌ 地圖檔案讀取失敗: {e}")
        return None

def get_dfs_exploration_path(graph, start):
    """使用 DFS 產生走遍所有死胡同的路徑"""
    visited = set()
    path = []
    last_new_node_idx = -1 

    def dfs(node):
        nonlocal last_new_node_idx
        visited.add(node)
        path.append(node)
        last_new_node_idx = len(path) - 1

        for direction in ['N', 'E', 'S', 'W']:
            if direction in graph[node]:
                neighbor = graph[node][direction]
                if neighbor not in visited:
                    dfs(neighbor)      
                    path.append(node)  

    dfs(start)
    # 只取到最後一個新發現的節點，不走回起點
    return path[:last_new_node_idx + 1]

def get_actions(graph, path, start_facing):
    """將節點路徑轉換為 W, A, S, D 指令序列"""
    actions = []
    current_facing = start_facing
    compass = ['N', 'E', 'S', 'W']
    for i in range(len(path) - 1):
        for direction, neighbor in graph[path[i]].items():
            if neighbor == path[i+1]:
                curr_idx = compass.index(current_facing)
                targ_idx = compass.index(direction)
                diff = (targ_idx - curr_idx) % 4
                
                # 轉向邏輯
                if diff == 1: actions.append('D')    # 右轉
                elif diff == 2: actions.append('S')  # 迴轉
                elif diff == 3: actions.append('A')  # 左轉
                
                actions.append('W') # 前進
                current_facing = direction
                break
    return actions

def main(mode: str):
    # 初始化計分板
    point = ScoreboardServer(TEAM_NAME, SERVER_URL)

    if mode == "0":
        log.info("🚀 啟動 DFS 全圖尋寶模式 (通訊強化版)")
        
        graph = load_graph(MAZE_FILE)
        if not graph: return

        # 1. 取得使用者輸入
        try:
            start_node = int(input("📍 請輸入起點編號: "))
            start_facing = input("🧭 初始朝向 (N/E/S/W): ").upper()
            if start_facing not in ['N', 'E', 'S', 'W']:
                log.error("❌ 朝向輸入錯誤")
                return
        except ValueError:
            log.error("❌ 請輸入正確的數字")
            return

        # 2. 計算路徑與動作
        path = get_dfs_exploration_path(graph, start_node)
        action_seq = get_actions(graph, path, start_facing)
        
        log.info(f"🗺️ DFS 路徑: {path}")
        log.info(f"🎯 指令總數: {len(action_seq)} -> {action_seq}")

        # 3. 建立藍牙連線
        try:
            ser = serial.Serial(BT_PORT, BAUD_RATE, timeout=0.1)
            log.info(f"📡 已連接至 {BT_PORT}，等待 3 秒讓連線穩定...")
            time.sleep(3)
            ser.reset_input_buffer()
            
            queue = list(action_seq)
            
            while queue:
                cmd = queue.pop(0)
                log.info(f"👉 發送指令: [{cmd}] (剩餘 {len(queue)} 個)")
                
                # 💡 關鍵：發送前清空緩衝，防止舊資料誤導
                ser.reset_input_buffer()
                ser.write(cmd.encode())
                
                # 4. 等待回傳 (K 或 UID)
                start_wait_time = time.time()
                buffer = ""
                received_k = False
                
                while time.time() - start_wait_time < 15:  # 15 秒執行超時
                    if ser.in_waiting > 0:
                        data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                        buffer += data
                        
                        # 處理 RFID UID
                        match = re.search(r'UID:([0-9A-F]+)', buffer)
                        if match:
                            uid = match.group(1)
                            log.info(f"💳 讀取到 UID: {uid}，正在上傳計分板...")
                            try:
                                point.add_UID(uid)
                            except Exception as e:
                                log.warning(f"⚠️ 上傳失敗: {e}")
                            buffer = buffer.replace(match.group(0), "")

                        # 判斷指令是否完成
                        if 'K' in buffer:
                            log.info(f" ✅ 指令 [{cmd}] 執行完畢")
                            received_k = True
                            break
                    time.sleep(0.02)
                
                if not received_k:
                    log.error(f"❌ 指令 [{cmd}] 等待超時！車子可能卡死或通訊中斷。")
                    break
                
                # 5. 🌟 關鍵：強制換氣延遲
                # 讓藍牙模組有足夠時間從「發送模式」切換回「接收模式」
                if queue:
                    log.info("⏳ 藍牙換氣中 (0.8s)...")
                    time.sleep(0.8)

            ser.close()
            log.info("🏁 任務執行結束")

        except serial.SerialException as e:
            log.error(f"❌ 無法開啟序列埠 {BT_PORT}: {e}")
        except Exception as e:
            log.error(f"❌ 發生未知的錯誤: {e}")

    else:
        log.error("無效的模式。請使用 '0'")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", help="0: treasure-hunting", type=str)
    args = parser.parse_args()
    main(args.mode)