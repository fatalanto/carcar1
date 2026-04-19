import csv
import time
import serial
import re # 🌟 新增正則表達式，用來精準捕捉 UID

# ================= 設定區 =================
SERIAL_PORT = 'COM7'  # 🌟 你的 ESP32 連接埠
BAUD_RATE = 9600
CSV_FILE = r'C:\Users\88693\Desktop\大學\大一下\車車\bfs1\maze.csv'
# ==========================================

def load_graph(filename):
    graph = {}
    try:
        with open(filename, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                node = int(row['index'])
                neighbors = {}
                if row['North']: neighbors['N'] = int(row['North'])
                if row['East']:  neighbors['E'] = int(row['East'])
                if row['South']: neighbors['S'] = int(row['South'])
                if row['West']:  neighbors['W'] = int(row['West'])
                graph[node] = neighbors
        return graph
    except FileNotFoundError:
        print(f"❌ 找不到檔案: {filename}")
        return None

def bfs(graph, start, goal):
    queue = [[start]]
    visited = {start}
    while queue:
        path = queue.pop(0)
        node = path[-1]
        if node == goal: return path
        for neighbor in graph[node].values():
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return None

def get_actions(graph, path, start_facing):
    actions = []
    current_facing = start_facing
    compass = ['N', 'E', 'S', 'W']
    for i in range(len(path) - 1):
        for direction, neighbor in graph[path[i]].items():
            if neighbor == path[i+1]:
                curr_idx = compass.index(current_facing)
                targ_idx = compass.index(direction)
                diff = (targ_idx - curr_idx) % 4
                if diff == 1: actions.append('D')
                elif diff == 2: actions.append('S')
                elif diff == 3: actions.append('A')
                actions.append('W')
                current_facing = direction
                break
    return actions

def main():
    graph = load_graph(CSV_FILE)
    if not graph: return

    print("--- 🚗 BFS 迷宮小車導航系統 (RFID 升級版) ---")
    try:
        start = int(input("📍 起點 (1-48): "))
        goal = int(input("🏁 終點 (1-48): "))
    except ValueError:
        print("❌ 請輸入數字！")
        return
        
    facing = input("🧭 初始朝向 (N/E/S/W): ").upper()
    if facing not in ['N', 'E', 'S', 'W']:
        print("❌ 朝向輸入錯誤！")
        return

    path = bfs(graph, start, goal)
    if not path:
        print("❌ 找不到路徑！")
        return
        
    action_seq = get_actions(graph, path, facing)
    print(f"\n✅ 路徑: {path}")
    print(f"🚀 指令序列: {action_seq}\n")

    try:
        print(f"📡 正在連接至 ESP32 ({SERIAL_PORT})...")
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)  
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        for cmd in action_seq:
            print(f"👉 發送 [{cmd}]...", end=" ", flush=True)
            ser.write(cmd.encode())
            
            start_time = time.time()
            buffer = "" # 🌟 用來收集藍牙碎片的緩衝區
            
            while True:
                if ser.in_waiting > 0:
                    res = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    buffer += res
                    
                    # 🌟 檢查有沒有讀到 RFID 標籤
                    match = re.search(r'UID:([0-9A-F]+)', buffer)
                    if match:
                        uid_val = match.group(1)
                        print(f"\n   💳 [讀取成功] 踩到 RFID 節點，卡號: {uid_val}", end="")
                        buffer = buffer.replace(match.group(0), "") # 顯示完就清掉
                        
                    if 'K' in buffer:
                        print(" ✅ 完成")
                        time.sleep(0.3) 
                        break
                
                if time.time() - start_time > 10:
                    print("\n⚠️ 警告：等待超時！未收到車子的 K 訊號。")
                    break
                    
        print("\n🏁 任務執行完畢！")
        ser.close()
        
    except serial.SerialException as e:
        print(f"\n❌ 通訊埠錯誤: {e}")
    except Exception as e:
        print(f"\n❌ 發生未知的錯誤: {e}")

if __name__ == "__main__":
    main()