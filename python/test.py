import argparse
import logging
import time
import serial
import re
import csv
from score import ScoreboardServer

# =========================
# 日誌設定
# =========================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# =========================
# 使用者設定
# =========================
TEAM_NAME = "MyTeam"
SERVER_URL = "http://carcar.ntuee.org/scoreboard"

BT_PORT = "COM6"
BAUD_RATE = 9600
MAZE_FILE = r"C:\Users\antho\OneDrive\桌面\carbfs\carcar1\midterm-project_2\python\big_maze_114.csv"

HANDSHAKE_WAIT = 2

# ⭐ 賽事真實總時間 65 秒
TOTAL_MATCH_TIME = 65.0
# ⭐ 演算法規劃時限 (保留 3 秒作為安全緩衝)
TIME_LIMIT = 62.0  

# =========================
# 讀迷宮圖
# =========================
def load_graph(filename):
    graph = {}
    with open(filename, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            node = int(row["index"])
            g_node = {}
            if row.get("North"): g_node["N"] = int(float(row["North"]))
            if row.get("East"):  g_node["E"] = int(float(row["East"]))
            if row.get("South"): g_node["S"] = int(float(row["South"]))
            if row.get("West"):  g_node["W"] = int(float(row["West"]))
            graph[node] = g_node
    return graph

# =========================
# 建立座標系與計算曼哈頓分數
# =========================
def build_coords_and_scores(graph, start_node):
    coords = {start_node: (0, 0)}
    queue = [start_node]
    visited = {start_node}

    while queue:
        curr = queue.pop(0)
        cx, cy = coords[curr]
        for d, nxt in graph[curr].items():
            if nxt not in visited:
                if d == 'N': coords[nxt] = (cx, cy + 1)
                elif d == 'S': coords[nxt] = (cx, cy - 1)
                elif d == 'E': coords[nxt] = (cx + 1, cy)
                elif d == 'W': coords[nxt] = (cx - 1, cy)
                visited.add(nxt)
                queue.append(nxt)

    scores = {}
    for node, (x, y) in coords.items():
        scores[node] = 10 * (abs(x) + abs(y))
    return scores

# =========================
# BFS 最短路徑搜尋 (點對點)
# =========================
def bfs_shortest_path(graph, start, goal):
    queue = [[start]]
    visited = {start}
    while queue:
        path = queue.pop(0)
        curr = path[-1]
        if curr == goal:
            return path
        for nxt in graph[curr].values():
            if nxt not in visited:
                visited.add(nxt)
                queue.append(path + [nxt])
    return []

# =========================
# 計算路徑的真實物理耗時與最終朝向
# =========================
def calc_path_time_and_facing(graph, path, start_facing):
    time_costs = {0: 0.765, 1: 1.17, 2: 0.955, 3: 1.17}
    comp = ["N", "E", "S", "W"]
    total_t = 0.0
    curr_f = start_facing
    
    for i in range(len(path) - 1):
        curr = path[i]
        nxt = path[i + 1]
        for d, n in graph[curr].items():
            if n == nxt:
                diff = (comp.index(d) - comp.index(curr_f)) % 4
                total_t += time_costs[diff]
                curr_f = d
                break
    return total_t, curr_f

# =========================
# ⭐ 智慧型指定打擊演算法 (保底回收貪婪策略)
# =========================
def get_smart_greedy_path(graph, start_node, start_facing, time_limit):
    scores = build_coords_and_scores(graph, start_node)
    
    # 1. 找出所有寶藏點 (地圖上的死胡同，且排除起點)
    treasures = [n for n, edges in graph.items() if len(edges) == 1 and n != start_node]
    
    # 2. 依分數由低到高排序
    treasures.sort(key=lambda n: scores[n])
    
    # 3. 戰術核心：扣除分數最低(最近)的兩個，放到最後走
    if len(treasures) >= 2:
        reserved_treasures = treasures[:2]   # 保底目標 (最後回收)
        active_treasures = treasures[2:]     # 優先進攻目標 (向外衝刺)
    else:
        reserved_treasures = []
        active_treasures = treasures
        
    full_path = [start_node]
    curr_node = start_node
    curr_facing = start_facing
    current_time = 0.0
    
    log.info(f"🗺️ 地圖掃描完畢，共發現 {len(treasures)} 個寶藏點 (死胡同)")
    log.info(f"🛡️ 戰術啟動：保留最後走的 2 個低分寶藏點為 -> {reserved_treasures}")
    log.info(f"⚔️ 優先進攻目標為 -> {active_treasures}")
    
    # 4. 先走 active (優先目標)，再走 reserved (保底目標)
    for phase, target_group in enumerate([active_treasures, reserved_treasures]):
        if phase == 1:
            log.info("🔔 優先目標已清空或超時，開始回收最後的保底寶藏！")
            
        while target_group:
            best_target = None
            best_path_to_target = []
            best_dist = float('inf')
            best_score = -1
            best_time_cost = 0
            best_final_facing = curr_facing
            
            # 評估群組內每一個寶藏點
            for t in target_group:
                p = bfs_shortest_path(graph, curr_node, t)
                if not p: continue
                
                dist = len(p) - 1  # 距離 (經過幾個節點)
                t_cost, f_facing = calc_path_time_and_facing(graph, p, curr_facing)
                
                # 戰術邏輯：越近越先走 -> 如果一樣近，先走分數高的
                if dist < best_dist:
                    best_dist = dist
                    best_score = scores[t]
                    best_target = t
                    best_path_to_target = p
                    best_time_cost = t_cost
                    best_final_facing = f_facing
                elif dist == best_dist:
                    if scores[t] > best_score:
                        best_score = scores[t]
                        best_target = t
                        best_path_to_target = p
                        best_time_cost = t_cost
                        best_final_facing = f_facing
                        
            if best_target is None:
                break
                
            # 檢查加上走到目標的時間後，是否會超過比賽總時限
            if current_time + best_time_cost > time_limit:
                log.info(f"⏳ 剩餘時間不足以走到寶藏 {best_target}，放棄此目標！")
                target_group.remove(best_target) # 這個點走不到，剔除它，試試看有沒有更近的
                continue
                
            # 確定目標，正式加入路徑
            target_group.remove(best_target)
            full_path.extend(best_path_to_target[1:]) # 避開重複加入當前節點
            curr_node = best_target
            curr_facing = best_final_facing
            current_time += best_time_cost
            
            log.info(f"🎯 鎖定寶藏 {best_target} (得分 {best_score}) | 耗時 {best_time_cost:.2f}s | 總剩餘時間 {time_limit - current_time:.2f}s")
            
    log.info(f"🏆 戰術路線規劃完成！總預估耗時: {current_time:.2f}s")
    return full_path

# =========================
# 路徑轉指令
# =========================
def get_actions(graph, path, start_facing):
    actions = []
    curr_f = start_facing
    comp = ["N", "E", "S", "W"]
    for i in range(len(path) - 1):
        curr = path[i]
        nxt = path[i + 1]
        for d, n in graph[curr].items():
            if n == nxt:
                diff = (comp.index(d) - comp.index(curr_f)) % 4
                if diff == 1: actions.append("D")
                elif diff == 2: actions.append("S")
                elif diff == 3: actions.append("A")
                actions.append("W")
                curr_f = d
                break
    return actions

# =========================
# 滑動視窗指令派發器
# =========================
def execute_commands_with_window(ser, point, action_seq):
    MAX_WINDOW = 3 
    in_flight = 0   
    cmd_idx = 0     
    total_cmds = len(action_seq)

    log.info("🚀 開始發送指令 (啟用 3 格緩衝區)...")
    
    # ⭐ 記錄碼錶啟動時間 (真實比賽時間計算起點)
    match_start_time = time.time()

    while in_flight < MAX_WINDOW and cmd_idx < total_cmds:
        cmd = action_seq[cmd_idx]
        ser.write((cmd + "\n").encode("utf-8"))
        ser.flush()
        in_flight += 1
        cmd_idx += 1

    buffer = ""
    last_receive_time = time.time()

    while in_flight > 0:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
            print(data, end="") 
            buffer += data
            last_receive_time = time.time()  

            while True:
                match = re.search(r"UID:([0-9A-F]+)", buffer)
                if not match: break
                uid = match.group(1)
                log.info(f"\n💳 UID: {uid}，正在上傳...")
                try:
                    point.add_UID(uid)
                except Exception as e:
                    log.warning(f"⚠️ UID 上傳失敗: {e}")
                buffer = buffer.replace(match.group(0), "", 1)

            # ===== 收到 K 的處理區塊 =====
            while "K" in buffer:
                buffer = buffer.replace("K", "", 1)
                in_flight -= 1  
                
                # ⭐ 計算並顯示剩餘時間 (以 65 秒為基準，避免出現負數)
                elapsed = time.time() - match_start_time
                remaining = max(0.0, TOTAL_MATCH_TIME - elapsed)

                if cmd_idx < total_cmds:
                    cmd = action_seq[cmd_idx]
                    ser.write((cmd + "\n").encode("utf-8"))
                    ser.flush()
                    in_flight += 1
                    cmd_idx += 1
                    log.info(f"✅ 收到 K，補發指令: [{cmd}] (車上: {in_flight}/{MAX_WINDOW}) | ⏱️ 比賽剩餘: {remaining:.2f}s")
                else:
                    log.info(f"✅ 收到 K，完成動作 (剩最後 {in_flight} 步) | ⏱️ 比賽剩餘: {remaining:.2f}s")

        if time.time() - last_receive_time > 8.0:
            log.error("\n❌ 車子超過 8 秒無回應 (Timeout)，可能卡住了！")
            break

        time.sleep(0.01)

# =========================
# 主程式
# =========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=BT_PORT)
    args = parser.parse_args()

    try:
        point = ScoreboardServer(TEAM_NAME, SERVER_URL)
        log.info("✅ 計分板連線成功")
    except Exception as e:
        log.error(f"❌ 網路連線失敗: {e}")

    try:
        graph = load_graph(MAZE_FILE)
    except Exception as e:
        log.error(f"❌ 迷宮檔讀取失敗: {e}")
        return

    try:
        start_node = 25 
        log.info(f"📍 固定起點編號: {start_node}")
        
        # =========================================
        # 自動判斷初始朝向
        # =========================================
        possible_exits = list(graph[start_node].keys())
        
        if len(possible_exits) == 1:
            start_facing = possible_exits[0]
            log.info(f"🧭 偵測到起點為死胡同，自動設定初始朝向: {start_facing}")
        else:
            log.warning("⚠️ 起點擁有多個出口，無法自動判斷，請手動輸入！")
            start_facing = input("🧭 初始朝向 (N/E/S/W): ").strip().upper()
            if start_facing not in ["N", "E", "S", "W"]: return

    except Exception as e:
        log.error(f"❌ 初始化設定錯誤: {e}")
        return

    # ⭐ 套用你專屬設計的戰術演算法
    path = get_smart_greedy_path(graph, start_node, start_facing, TIME_LIMIT)
    action_seq = get_actions(graph, path, start_facing)

    log.info(f"🛣️ 戰術節點路徑: {path}")
    log.info(f"🎯 戰術指令序列: {action_seq}")
    log.info(f"📝 總共執行 {len(action_seq)} 個動作")

    try:
        ser = serial.Serial(args.port, BAUD_RATE, timeout=0.1)
        log.info(f"📡 已連線 {args.port}")
        time.sleep(HANDSHAKE_WAIT)
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception as e:
        log.error(f"❌ 無法開啟序列埠: {e}")
        return

    try:
        execute_commands_with_window(ser, point, action_seq)
        log.info("🏁 任務結束，完美抵達終點！")
    except KeyboardInterrupt:
        log.warning("⛔ 使用者中止")
    finally:
        ser.close()

if __name__ == "__main__":
    main()