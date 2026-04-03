#include <SPI.h>
#include <MFRC522.h>

// --- HM-10 藍牙設定 ---
#define CUSTOM_NAME "11111" 
long baudRates[] = {9600, 19200, 38400, 57600, 115200, 4800, 2400, 1200, 230400};
bool moduleReady = false;

// --- RFID (MFRC522) 設定 ---
#define RST_PIN 49
#define SS_PIN 53
// 這裡改用靜態宣告物件，比用指標 (new) 更節省記憶體且不易出錯
MFRC522 mfrc522(SS_PIN, RST_PIN); 

void setup() {
  Serial.begin(115200); // 電腦 USB 監控視窗 (看 Debug 訊息用)
  while (!Serial);

  // 1. 初始化 SPI 與 RFID 模組
  SPI.begin();
  mfrc522.PCD_Init();
  Serial.println(F("RFID Module Initialized."));

  // 2. 初始化 HM-10 藍牙模組
  Serial.println("Initializing HM-10...");
  for (int i = 0; i < 9; i++) {
    Serial.print("Testing baud rate: ");
    Serial.println(baudRates[i]);
    
    Serial3.begin(baudRates[i]);
    Serial3.setTimeout(100);
    delay(100);

    Serial3.print("AT"); 
    if (waitForResponse("OK", 800)) {
      Serial.println("HM-10 detected and ready.");
      moduleReady = true;
      break; 
    } else {
      Serial3.end();
      delay(100);
    }
  }

  if (moduleReady) {
    Serial.println("Configuring HM-10...");
    sendATCommand("AT+RENEW"); 
    delay(500);
    
    String nameCmd = "AT+NAME" + String(CUSTOM_NAME);
    sendATCommand(nameCmd.c_str()); 
    sendATCommand("AT+NOTI1"); 
    sendATCommand("AT+RESET"); 
    delay(1000);
    
    Serial3.begin(9600); // 模組重置後回到預設的 9600 鮑率
    Serial.println("HM-10 Ready! Waiting for Bluetooth connection...");
  } else {
    Serial.println("Failed to detect HM-10. Check wiring.");
  }
}

void loop() {
  // --- 1. 藍牙與 USB 的雙向除錯通道 (保留您原本的設計) ---
  if (Serial3.available()) {
    Serial.write(Serial3.read()); // 將藍牙收到的訊息印到電腦螢幕
  }
  if (Serial.available()) {
    Serial3.write(Serial.read()); // 將電腦打的字傳給藍牙
  }

  // --- 2. 偵測並讀取 RFID 卡片 ---
  if (!mfrc522.PICC_IsNewCardPresent() || !mfrc522.PICC_ReadCardSerial()) {
    return; // 沒有卡片就提早結束這回合
  }

  // 3. 將 UID 轉換為乾淨的十六進位字串 (例如 "A1B2C3D4")
  String uidString = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) {
      uidString += "0"; // 補零，確保格式整齊
    }
    uidString += String(mfrc522.uid.uidByte[i], HEX);
  }
  uidString.toUpperCase(); 

  // 4. 顯示在 USB 螢幕 (確認 Arduino 有讀到)
  Serial.print("Card Scanned UID: ");
  Serial.println(uidString);

  // 5. 【關鍵】透過 HM-10 藍牙傳送給 Python 端！
  if (moduleReady) {
    Serial3.println(uidString); // println 會自動加上換行符號 \r\n
  }

  // 6. 停止卡片讀取，避免同一張卡瘋狂連續觸發
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

// --- 輔助函式 ---
void sendATCommand(const char* command) {
  Serial3.print(command);
  waitForResponse("", 1000); 
}

bool waitForResponse(const char* expected, unsigned long timeout) {
  unsigned long start = millis();
  Serial3.setTimeout(timeout);
  String response = Serial3.readString();
  if (response.length() > 0) {
    Serial.print("HM10 Response: ");
    Serial.println(response);
  }
  return (response.indexOf(expected) != -1);
}