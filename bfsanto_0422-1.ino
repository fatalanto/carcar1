#include <SPI.h>
#include <MFRC522.h>

// =====================
// 感測器腳位
// =====================
#define S1 A3
#define S2 A4
#define S3 A5
#define S4 A6
#define S5 A7

// =====================
// 馬達腳位與參數
// =====================
int PWMA = 10, AIN2 = 6, AIN1 = 7;
int BIN1 = 8, BIN2 = 9, PWMB = 11;

int Tp = 180;
double Kp = 40, Kd = 60, lastError = 0;
int mid = 80;

// =====================
// RFID 設定
// =====================
#define RST_PIN 49
#define SS_PIN 53
MFRC522 mfrc522(SS_PIN, RST_PIN);

String lastUID = "";
unsigned long lastUIDTime = 0;

// =====================
// ⭐ 系統狀態記憶體
// =====================
String cmdQueue = "";       // 車上的指令緩衝佇列 (最多存 3 個)
char lastCommand = 'W';     // 記住上一次的動作，預設為 W 讓起步能有逃脫期

// =====================
// Setup
// =====================
void setup() {
  Serial.begin(9600);
  Serial3.begin(9600);

  pinMode(13, OUTPUT);
  pinMode(S1, INPUT); pinMode(S2, INPUT); pinMode(S3, INPUT); pinMode(S4, INPUT); pinMode(S5, INPUT);
  pinMode(PWMA, OUTPUT); pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT); pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT);

  SPI.begin();
  mfrc522.PCD_Init();

  for (int i = 0; i < 3; i++) {
    digitalWrite(13, HIGH); delay(100); digitalWrite(13, LOW); delay(100);
  }
}

// =====================
// RFID 掃描防連刷
// =====================
void scanRFID() {
  if (!mfrc522.PICC_IsNewCardPresent()) return;
  if (!mfrc522.PICC_ReadCardSerial()) return;

  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  if (uid == lastUID && millis() - lastUIDTime < 1500) {
    mfrc522.PICC_HaltA(); mfrc522.PCD_StopCrypto1();
    return;
  }
  lastUID = uid;
  lastUIDTime = millis();
  
  Serial3.print("UID:" + uid + ",");
  mfrc522.PICC_HaltA(); mfrc522.PCD_StopCrypto1();
}

// =====================
// 馬達控制
// =====================
void MotorWriting(int vL, int vR) {
  if (vL >= 0) { digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW); analogWrite(PWMA, constrain(vL, 0, 255)); } 
  else { digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH); analogWrite(PWMA, constrain(-vL, 0, 255)); }
  if (vR >= 0) { digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW); analogWrite(PWMB, constrain(vR, 0, 255)); } 
  else { digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH); analogWrite(PWMB, constrain(-vR, 0, 255)); }
}

// =====================
// ⭐ 非阻塞收指令模組
// =====================
void checkSerialAndFillQueue() {
  while (Serial3.available() && cmdQueue.length() < 3) {
    char c = Serial3.read();
    if (c == 'W' || c == 'A' || c == 'D' || c == 'S') {
      cmdQueue += c;
    }
  }
}

// =====================
// 動作：前進一格 (W)
// =====================
void moveOneNode() {
  MotorWriting(100, 100); delay(40);
  unsigned long t = millis();
  
  // 紀錄起步時的 UID 時間，用來判斷途中是否吃到新寶藏
  unsigned long startUIDTime = lastUIDTime; 

  // ⭐ 動態逃脫期：如果上一步是直走(W)，這步起步需要閉眼 300ms 防止重複觸發路口
  // 如果上一步是轉彎(A/D/S)，車身已經離開路口，不需要閉眼 (0ms)
  unsigned long blindTime = (lastCommand == 'W') ? 500 : 0;

  while (true) {
    scanRFID();
    checkSerialAndFillQueue(); // 一邊跑一邊把剩下的指令收進 Queue

    // 1. 掃到新 UID 提早煞車機制
    if (lastUIDTime != startUIDTime) {
      MotorWriting(0, 0); 
      delay(40);
      lastError = 0;
      return; 
    }

    int s1 = analogRead(S1); int s5 = analogRead(S5);

    // 2. ⭐ 護盾時間過了，才允許偵測十字路口
    if (millis() - t >= blindTime) {
      if (s1 >= mid && s5 >= mid) {
        lastError = 0;
        return; // 正常到路口結束，不煞車 (維持流暢接軌)
      }
    }

    // 3. PID 循跡
    int s2 = analogRead(S2); int s3 = analogRead(S3); int s4 = analogRead(S4);
    double sum = s1 + s2 + s3 + s4 + s5 + 1;
    double e = (-2.0 * s1 + -1.0 * s2 + 0.0 * s3 + 1.0 * s4 + 2.0 * s5) / sum;
    double pCorr = Kp * e + Kd * (e - lastError);
    MotorWriting(Tp + pCorr, Tp - pCorr);
    lastError = e;

    if (millis() - t > 3000) return; // 超時保護
  }
}

// =====================
// 動作：圓角左轉 (A) (感測器狀態機版)
// =====================
void turnLeft90() {
  lastError = 0;  
  int sig = 0;
  while (true) {
    checkSerialAndFillQueue();
    MotorWriting(20, 120);
    
    if (sig == 0) {
      if (analogRead(S3) < mid) sig = 1; // 離開舊的黑線了
    }
    if (sig == 1) {
      if (analogRead(S3) > mid) return;  // 踩到新的黑線了，結束轉彎
    }
  }
}

// =====================
// 動作：圓角右轉 (D) (感測器狀態機版)
// =====================
void turnRight90() {
  lastError = 0;  
  int sig = 0;
  while (true) {
    checkSerialAndFillQueue();
    MotorWriting(120, 20);
    
    if (sig == 0) {
      if (analogRead(S3) < mid) sig = 1;
    }
    if (sig == 1) {
      if (analogRead(S3) > mid) return;
    }
  }
}

// =====================
// 動作：原地迴轉 (S)
// =====================
void turnAround() {
  lastError = 0;
  MotorWriting(130,-130);
  delay(450);
  while (analogRead(S4) < mid) {       // 尋找黑線 (S3比較準確)
    checkSerialAndFillQueue();
    MotorWriting(60, -60); 
    scanRFID();
  }
  MotorWriting(0, 0); // 迴轉完停穩
}

// =====================
// 主迴圈 (記憶體總管)
// =====================
void loop() {
  scanRFID();
  checkSerialAndFillQueue();

  // 如果車子有空，且佇列裡有指令，就拿出第一個來執行
  if (cmdQueue.length() > 0) {
    digitalWrite(13, HIGH);
    
    char currentCmd = cmdQueue[0];    // 讀取第一個指令
    cmdQueue.remove(0, 1);            // 把它從記憶體中刪掉 (Pop)

    // 執行對應的動作
    if (currentCmd == 'W') moveOneNode();
    else if (currentCmd == 'A') turnLeft90();
    else if (currentCmd == 'D') turnRight90();
    else if (currentCmd == 'S') turnAround();

    // ⭐ 記住剛剛做了什麼，交接給下一步判定護盾！
    lastCommand = currentCmd;

    // 動作「徹底完成」後，統一回報 K 給電腦，請電腦補貨
    Serial3.print('K');
    digitalWrite(13, LOW);
  }

  // 二度確認收件狀況，確保判斷煞車前 Queue 是最新的
  checkSerialAndFillQueue(); 

  // ⭐⭐ 終點煞車機制：如果做完動作後佇列空了，立刻煞車！
  if (cmdQueue.length() == 0) {
    MotorWriting(0, 0); 
  }
}