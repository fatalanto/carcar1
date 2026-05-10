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
MAZE_FILE = "big_maze_114.csv"  # 換成你的檔案路徑

HANDSHAKE_WAIT = 5

# ⭐ 賽事真實總時間 65 秒
TOTAL_MATCH_TIME = 65.0
# ⭐ 演算法規劃時限 (保留 3 秒作為安全緩衝)
TIME_LIMIT = 62.0  

# =========================
# 1. 讀取迷宮與實體距離權重 (防空白當機版)
# =========================
def load_graph(filename):
    graph = {}
    weights = {}  # 紀錄兩點之間的實際距離 (ND, SD, WD, ED)
    with open(filename, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 防呆：跳過完全空白的行
            if not row.get("index") or not row["index"].strip():
                continue
                
            node = int(row["index"])
            g_node = {}
            
            # 安全解析函數：處理 CSV 裡的空白儲存格
            def parse_edge(dir_key, dist_key, face):
                val = row.get(dir_key)
                if val and val.strip():  # 確認有連線
                    nxt = int(float(val))
                    g_node[face] = nxt
                    
                    # 讀取距離，如果 CSV 沒寫則預設為 3.0
                    dist_val = row.get(dist_key)
                    if dist_val and dist_val.strip():
                        weights[(node, nxt)] = float(dist_val)
                    else:
                        weights[(node, nxt)] = 3.0 
                        
            parse_edge("North", "ND", "N")
            parse_edge("South", "SD", "S")
            parse_edge("West", "WD", "W")
            parse_edge("East", "ED", "E")
            
            graph[node] = g_node
    return graph, weights

# =========================
# 2. 建立精準座標系與計算曼哈頓分數
# =========================
def build_coords_and_scores(graph, weights, start_node):
    coords = {start_node: (0, 0)}
    queue = [start_node]
    visited = {start_node}

    while queue:
        curr = queue.pop(0)
        cx, cy = coords[curr]
        for d, nxt in graph[curr].items():
            if nxt not in visited:
                # 根據 CSV 裡的 ND/SD/WD/ED 延伸正確的實體距離
                dist = weights.get((curr, nxt), 3.0)
                if d == 'N': coords[nxt] = (cx, cy + dist)
                elif d == 'S': coords[nxt] = (cx, cy - dist)
                elif d == 'E': coords[nxt] = (cx + dist, cy)
                elif d == 'W': coords[nxt] = (cx - dist, cy)
                visited.add(nxt)
                queue.append(nxt)

    scores = {}
    for node, (x, y) in coords.items():
        # 分數 = 曼哈頓距離 * 10 (依照真實比例計算)
        scores[node] = int(10 * (abs(x) + abs(y)))
    return scores

# =========================
# 3. BFS 最短路徑搜尋
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
# 4. 動態計算物理時間與最終朝向 (適應不同長度路線)
# =========================
def calc_path_time_and_facing(graph, weights, path, start_facing):
    straight_time_base = 0.765
    turn_time = 0.405
    uturn_time = 0.190
    
    comp = ["N", "E", "S", "W"]
    total_t = 0.0
    curr_f = start_facing
    
    for i in range(len(path) - 1):
        curr = path[i]
        nxt = path[i + 1]
        
        # 取得這段路的真實長度比例
        dist = weights.get((curr, nxt), 3.0)
        dist_ratio = dist / 3.0
        
        for d, n in graph[curr].items():
            if n == nxt:
                diff = (comp.index(d) - comp.index(curr_f)) % 4
                
                # 計算動態耗時：動作時間 + (直走時間 * 距離比例)
                if diff == 0:
                    total_t += straight_time_base * dist_ratio
                elif diff == 1 or diff == 3:
                    total_t += turn_time + (straight_time_base * dist_ratio)
                elif diff == 2:
                    total_t += uturn_time + (straight_time_base * dist_ratio)
                    
                curr_f = d
                break
    return total_t, curr_f

# =========================
# 5. ⭐ 智慧型指定打擊演算法 (保底回收貪婪策略)
# =========================
def get_smart_greedy_path(graph, weights, start_node, start_facing, time_limit):
    scores = build_coords_and_scores(graph, weights, start_node)
    
    treasures = [n for n, edges in graph.items() if len(edges) == 1 and n != start_node]
    treasures.sort(key=lambda n: scores[n])
    
    if len(treasures) >= 2:
        reserved_treasures = treasures[:2]   
        active_treasures = treasures[2:]     
    else:
        reserved_treasures = []
        active_treasures = treasures
        
    full_path = [start_node]
    curr_node = start_node
    curr_facing = start_facing
    current_time = 0.0
    
    log.info(f"🗺️ 掃描完畢，發現 {len(treasures)} 個死胡同寶藏點")
    log.info(f"🛡️ 戰術啟動：保留 2 個低分寶藏為 -> {reserved_treasures}")
    log.info(f"⚔️ 優先進攻高分目標 -> {active_treasures}")
    
    for phase, target_group in enumerate([active_treasures, reserved_treasures]):
        if phase == 1:
            log.info("🔔 開始回收最後的保底寶藏！")
            
        while target_group:
            best_target = None
            best_path_to_target = []
            best_dist = float('inf')
            best_score = -1
            best_time_cost = 0
            best_final_facing = curr_facing
            
            for t in target_group:
                p = bfs_shortest_path(graph, curr_node, t)
                if not p: continue
                
                dist = len(p) - 1 
                t_cost, f_facing = calc_path_time_and_facing(graph, weights, p, curr_facing)
                
                # 戰術：越近越先走 -> 一樣近挑高分的
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
                
            if current_time + best_time_cost > time_limit:
                log.info(f"⏳ 剩餘時間不足走到寶藏 {best_target}，放棄目標！")
                target_group.remove(best_target) 
                continue
                
            target_group.remove(best_target)
            full_path.extend(best_path_to_target[1:]) 
            curr_node = best_target
            curr_facing = best_final_facing
            current_time += best_time_cost
            
            log.info(f"🎯 鎖定寶藏 {best_target} (得分 {best_score}) | 耗時 {best_time_cost:.2f}s | 總剩餘時間 {time_limit - current_time:.2f}s")
            
    log.info(f"🏆 戰術路線規劃完成！總預估耗時: {current_time:.2f}s")
    return full_path

# =========================
# 6. 路徑轉指令
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
# 7. ⭐ 一次性批次傳輸 (全速無縫接軌版)
# =========================
def execute_all_at_once(ser, point, action_seq):
    # 將陣列合併成一條超長字串
    full_cmd_string = "".join(action_seq)
    total_cmds = len(full_cmd_string)
    
    log.info(f"🚀 一次性發送完整劇本給車子: [{full_cmd_string}] (共 {total_cmds} 步)")
    
    # 一口氣全部傳輸給車子
    ser.write((full_cmd_string + "\n").encode("utf-8"))
    ser.flush()

    match_start_time = time.time()
    buffer = ""
    
    log.info("🎧 指令發送完畢！切換為全職監聽模式，等待 UID 上傳...")

    while True:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
            print(data, end="") 
            buffer += data

            # ===== 攔截並上傳 UID =====
            while True:
                match = re.search(r"UID:([0-9A-F]+)", buffer)
                if not match: break
                uid = match.group(1)
                
                # ⭐ 計算並顯示比賽剩餘時間
                elapsed = time.time() - match_start_time
                remaining = max(0.0, TOTAL_MATCH_TIME - elapsed)
                
                log.info(f"\n💳 UID: {uid}，正在上傳... (⏱️ 比賽剩餘: {remaining:.2f}s)")
                try:
                    point.add_UID(uid)
                except Exception as e:
                    log.warning(f"⚠️ UID 上傳失敗: {e}")
                    
                buffer = buffer.replace(match.group(0), "", 1)

            # ===== 攔截完賽廣播 DONE =====
            if "DONE" in buffer:
                final_elapsed = time.time() - match_start_time
                log.info(f"\n🏁 車子回報：全線跑完！總實際耗時: {final_elapsed:.2f}s")
                break

        # Timeout 保護機制
        if time.time() - match_start_time > (TOTAL_MATCH_TIME + 5.0):
            log.error(f"\n❌ 超過 {TOTAL_MATCH_TIME + 5.0} 秒車子無回應 (Timeout)，強制結束監聽！")
            break

        time.sleep(0.01)

# =========================
# 8. 主程式
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
        graph, weights = load_graph(MAZE_FILE)
    except Exception as e:
        log.error(f"❌ 迷宮檔讀取失敗: {e}")
        return

    try:
        start_node = 25 
        log.info(f"📍 固定起點編號: {start_node}")
        
        # 自動判斷初始朝向
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

    # 執行戰術演算法
    path = get_smart_greedy_path(graph, weights, start_node, start_facing, TIME_LIMIT)
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
        # ⭐ 改用一次性批次傳輸函式
        execute_all_at_once(ser, point, action_seq)
        log.info("🏁 任務結束，完美抵達終點！")
    except KeyboardInterrupt:
        log.warning("⛔ 使用者中止")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
