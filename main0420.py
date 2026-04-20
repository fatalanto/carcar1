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

BT_PORT = "COM7"          # ESP32 藍牙序列埠
BAUD_RATE = 9600

MAZE_FILE = r"C:\Users\88693\Desktop\大學\大一下\車車\bfs1\medium_maze.csv"

HANDSHAKE_WAIT = 5        # 開啟序列埠後等待 ESP32
CMD_TIMEOUT = 3           # 每個指令最多等幾秒
STEP_DELAY = 0.05         # 每步之間延遲（越小越快）


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

            if row.get("North"):
                g_node["N"] = int(float(row["North"]))

            if row.get("East"):
                g_node["E"] = int(float(row["East"]))

            if row.get("South"):
                g_node["S"] = int(float(row["South"]))

            if row.get("West"):
                g_node["W"] = int(float(row["West"]))

            graph[node] = g_node

    return graph


# =========================
# DFS 路徑
# =========================
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


# =========================
# 路徑轉指令
# W = 前進
# A = 左轉
# D = 右轉
# S = 迴轉
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

                if diff == 1:
                    actions.append("D")
                elif diff == 2:
                    actions.append("S")
                elif diff == 3:
                    actions.append("A")

                actions.append("W")
                curr_f = d
                break

    return actions


# =========================
# 傳送單一指令並等待 K
# =========================
def send_command(ser, cmd, point):
    log.info(f"👉 傳送指令: [{cmd}]")

    # 清空舊資料
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # 加換行，ESP32 更容易解析
    ser.write((cmd + "\n").encode("utf-8"))
    ser.flush()

    start_t = time.time()
    buffer = ""

    while time.time() - start_t < CMD_TIMEOUT:

        if ser.in_waiting > 0:
            data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")

            print(data, end="")
            buffer += data

            # ===== 偵測 UID =====
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

            # ===== 指令完成 =====
            if "K" in buffer:
                log.info(f"✅ 指令 [{cmd}] 成功")
                return True

        time.sleep(0.01)

    return False


# =========================
# 主程式
# =========================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default=BT_PORT)
    args = parser.parse_args()

    # --- 連線計分板 ---
    try:
        point = ScoreboardServer(TEAM_NAME, SERVER_URL)
        log.info("✅ 計分板連線成功")
    except Exception as e:
        log.error(f"❌ 網路連線失敗: {e}")
        return

    # --- 載入迷宮 ---
    try:
        graph = load_graph(MAZE_FILE)
    except Exception as e:
        log.error(f"❌ 迷宮檔讀取失敗: {e}")
        return

    # --- 使用者輸入 ---
    try:
        start_node = int(input("📍 起點編號: "))
        start_facing = input("🧭 初始朝向 (N/E/S/W): ").strip().upper()

        if start_facing not in ["N", "E", "S", "W"]:
            log.error("❌ 朝向輸入錯誤")
            return

    except Exception:
        log.error("❌ 輸入錯誤")
        return

    # --- 計算路徑 ---
    path = get_dfs_exploration_path(graph, start_node)
    action_seq = get_actions(graph, path, start_facing)

    log.info(f"🛣️ DFS 節點路徑: {path}")
    log.info(f"🎯 指令序列: {action_seq}")

    # --- 開啟藍牙 ---
    try:
        ser = serial.Serial(args.port, BAUD_RATE, timeout=0.1)

        log.info(f"📡 已連線 {args.port}")
        log.info(f"⏳ 等待 ESP32 啟動 {HANDSHAKE_WAIT} 秒...")
        time.sleep(HANDSHAKE_WAIT)

        ser.reset_input_buffer()
        ser.reset_output_buffer()

    except Exception as e:
        log.error(f"❌ 無法開啟序列埠: {e}")
        return

    # --- 執行所有指令 ---
    try:
        for cmd in action_seq:
            ok = send_command(ser, cmd, point)

            if not ok:
                log.error(f"❌ 指令 [{cmd}] 超時，停止執行")
                break

            time.sleep(STEP_DELAY)

        log.info("🏁 任務結束")

    except KeyboardInterrupt:
        log.warning("⛔ 使用者中止")

    except Exception as e:
        log.error(f"❌ 執行錯誤: {e}")

    finally:
        ser.close()
        log.info("🔌 序列埠已關閉")


# =========================
# 啟動
# =========================
if __name__ == "__main__":
    main()
