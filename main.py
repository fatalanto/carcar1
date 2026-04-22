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
MAZE_FILE = r"C:\Users\antho\OneDrive\桌面\carbfs\carcar1\midterm-project_2\python\medium_maze.csv"

HANDSHAKE_WAIT = 5

# =========================
# 讀迷宮圖 & 路徑規劃 (與原本相同)
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

def get_dfs_exploration_path(graph, start):
    visited = set()
    path = []
    last_idx = -1
    def dfs(node):
        nonlocal last_idx
        visited.add(node)
        path.append(node)
        last_idx = len(path) - 1
        for d in ["N", "E", "S", "W"]:
            if d in graph[node]:
                nxt = graph[node][d]
                if nxt not in visited:
                    dfs(nxt)
                    path.append(node)
    dfs(start)
    return path[:last_idx + 1]

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
# ⭐ 新增：滑動視窗指令派發器
# =========================
def execute_commands_with_window(ser, point, action_seq):
    MAX_WINDOW = 3  # 車上最多暫存 3 個指令
    in_flight = 0   # 紀錄目前車上還有幾個未完成的指令
    cmd_idx = 0     # 紀錄清單發送到第幾個了
    total_cmds = len(action_seq)

    log.info("🚀 開始發送指令 (啟用 3 格緩衝區)...")

    # 1. 遊戲開始，先一口氣把車上的 3 個緩衝區塞滿
    while in_flight < MAX_WINDOW and cmd_idx < total_cmds:
        cmd = action_seq[cmd_idx]
        ser.write((cmd + "\n").encode("utf-8"))
        ser.flush()
        in_flight += 1
        cmd_idx += 1
        log.info(f"📦 預塞指令: [{cmd}] (車上進度: {in_flight}/{MAX_WINDOW})")

    # 2. 開始監聽車子回報，並隨時「補貨」
    buffer = ""
    last_receive_time = time.time()

    while in_flight > 0:
        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
            print(data, end="") # 讓你在終端機能看到回傳
            buffer += data
            last_receive_time = time.time()  # 有收到東西就重置超時時鐘

            # ===== 偵測並處理 UID =====
            while True:
                match = re.search(r"UID:([0-9A-F]+)", buffer)
                if not match:
                    break
                uid = match.group(1)
                log.info(f"\n💳 UID: {uid}，正在上傳...")
                try:
                    point.add_UID(uid)
                except Exception as e:
                    log.warning(f"⚠️ UID 上傳失敗: {e}")
                buffer = buffer.replace(match.group(0), "", 1)

            # ===== 偵測到 K (車子消化完一個動作了) =====
            while "K" in buffer:
                buffer = buffer.replace("K", "", 1)
                in_flight -= 1  # 車上空出一個位子了

                # 如果總指令還沒發完，立刻補發一個過去，維持滿載
                if cmd_idx < total_cmds:
                    cmd = action_seq[cmd_idx]
                    ser.write((cmd + "\n").encode("utf-8"))
                    ser.flush()
                    in_flight += 1
                    cmd_idx += 1
                    log.info(f"🔄 補發指令: [{cmd}] (車上維持: {in_flight}/{MAX_WINDOW})")
                else:
                    log.info(f"✅ 車子完成動作 (剩餘最後 {in_flight} 步收尾)")

        # Timeout 保護 (超過 8 秒車子都沒動作，可能卡住了)
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
        return

    try:
        graph = load_graph(MAZE_FILE)
    except Exception as e:
        log.error(f"❌ 迷宮檔讀取失敗: {e}")
        return

    try:
        start_node = int(input("📍 起點編號: "))
        start_facing = input("🧭 初始朝向 (N/E/S/W): ").strip().upper()
        if start_facing not in ["N", "E", "S", "W"]: return
    except Exception:
        return

    path = get_dfs_exploration_path(graph, start_node)
    action_seq = get_actions(graph, path, start_facing)

    log.info(f"🛣️ DFS 節點路徑: {path}")
    log.info(f"🎯 指令序列: {action_seq}")

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
        # 改呼叫我們寫好的新函式
        execute_commands_with_window(ser, point, action_seq)
        log.info("🏁 任務結束，完美抵達終點！")
    except KeyboardInterrupt:
        log.warning("⛔ 使用者中止")
    finally:
        ser.close()

if __name__ == "__main__":
    main()