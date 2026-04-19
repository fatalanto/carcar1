import argparse
import logging
import time
import serial
import re
import csv
from score import ScoreboardServer

# 設定日誌
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# --- 設定區 ---
TEAM_NAME = "MyTeam"
SERVER_URL = "http://carcar.ntuee.org/scoreboard"
BT_PORT = "COM7"  # 你的 ESP32 埠
BAUD_RATE = 9600
MAZE_FILE = r"C:\Users\88693\Desktop\大學\大一下\車車\bfs1\maze.csv"

def load_graph(filename):
    graph = {}
    with open(filename, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            node = int(row['index'])
            g_node = {}
            if row.get('North'): g_node['N'] = int(float(row['North']))
            if row.get('East'):  g_node['E'] = int(float(row['East']))
            if row.get('South'): g_node['S'] = int(float(row['South']))
            if row.get('West'):  g_node['W'] = int(float(row['West']))
            graph[node] = g_node
    return graph

def get_dfs_exploration_path(graph, start):
    visited = set(); path = []; last_idx = -1
    def dfs(node):
        nonlocal last_idx; visited.add(node); path.append(node); last_idx = len(path) - 1
        for d in ['N', 'E', 'S', 'W']:
            if d in graph[node] and graph[node][d] not in visited:
                dfs(graph[node][d]); path.append(node)
    dfs(start); return path[:last_idx + 1]

def get_actions(graph, path, start_facing):
    actions = []; curr_f = start_facing; comp = ['N', 'E', 'S', 'W']
    for i in range(len(path) - 1):
        for d, n in graph[path[i]].items():
            if n == path[i+1]:
                diff = (comp.index(d) - comp.index(curr_f)) % 4
                if diff == 1: actions.append('D')
                elif diff == 2: actions.append('S')
                elif diff == 3: actions.append('A')
                actions.append('W'); curr_f = d; break
    return actions

def main():
    # 🌟 初始化連線版計分板 (必須有網路)
    try:
        point = ScoreboardServer(TEAM_NAME, SERVER_URL)
        log.info("✅ 計分板連線成功")
    except Exception as e:
        log.error(f"❌ 網路連線失敗: {e}")
        return

    graph = load_graph(MAZE_FILE)
    start_node = int(input("📍 起點編號: "))
    start_facing = input("🧭 初始朝向: ").upper()
    
    path = get_dfs_exploration_path(graph, start_node)
    action_seq = get_actions(graph, path, start_facing)
    log.info(f"🎯 指令序列: {action_seq}")

    try:
        ser = serial.Serial(BT_PORT, BAUD_RATE, timeout=0.1)
        log.info("📡 等待 ESP32 握手 (5秒)...")
        time.sleep(5)
        ser.reset_input_buffer()

        queue = list(action_seq)
        while queue:
            cmd = queue.pop(0)
            log.info(f"👉 傳送指令: [{cmd}]")
            
            ser.reset_input_buffer()
            ser.write(cmd.encode('utf-8')) # 🌟 單個字元發送
            
            start_t = time.time()
            buffer = ""
            success = False
            
            while time.time() - start_t < 15:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    print(data, end="") # 🌟 印出 ESP32 轉發紀錄
                    buffer += data
                    
                    match = re.search(r'UID:([0-9A-F]+)', buffer)
                    if match:
                        log.info(f"\n💳 UID: {match.group(1)}，正在上傳...")
                        try: point.add_UID(match.group(1))
                        except: pass
                        buffer = buffer.replace(match.group(0), "")

                    if 'K' in buffer:
                        log.info(f" ✅ 指令 [{cmd}] 成功")
                        success = True; break
                time.sleep(0.01)
            
            if not success:
                log.error("❌ 指令超時斷聯")
                break
            time.sleep(1.2) # 換氣延遲

        ser.close()
    except Exception as e:
        log.error(f"❌ 錯誤: {e}")

if __name__ == "__main__":
    main()
