#include <SPI.h>
#include <MFRC522.h>

#define S1 A3
#define S2 A4
#define S3 A5
#define S4 A6
#define S5 A7

int PWMA = 10, AIN2 = 6, AIN1 = 7;
int BIN1 = 8, BIN2 = 9, PWMB = 11;

int Tp = 135;
double Kp = 40, Kd = 60, lastError = 0;
int mid = 80;

#define RST_PIN 49
#define SS_PIN 53
MFRC522 mfrc522(SS_PIN, RST_PIN);

String lastUID = "";
unsigned long lastUIDTime = 0;

// ⭐ 新增：車上的指令記憶體 (佇列)
String cmdQueue = "";

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

void MotorWriting(int vL, int vR) {
  if (vL >= 0) { digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW); analogWrite(PWMA, constrain(vL, 0, 255)); } 
  else { digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH); analogWrite(PWMA, constrain(-vL, 0, 255)); }
  if (vR >= 0) { digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW); analogWrite(PWMB, constrain(vR, 0, 255)); } 
  else { digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH); analogWrite(PWMB, constrain(-vR, 0, 255)); }
}

// 將收指令的動作獨立出來
void checkSerialAndFillQueue() {
  while (Serial3.available() && cmdQueue.length() < 3) {
    char c = Serial3.read();
    if (c == 'W' || c == 'A' || c == 'D' || c == 'S') {
      cmdQueue += c;
    }
  }
}
// =====================
// 動作函式 (拔除所有 print('K')，變回純粹的動作)
// =====================
void moveOneNode() {
  MotorWriting(100, 100); delay(40);
  unsigned long t = millis();
  while (true) {
    scanRFID();
    checkSerialAndFillQueue();
    int s1 = analogRead(S1); int s5 = analogRead(S5);

    if (s1 >= mid && s5 >= mid) {
      lastError = 0;
      return;      // 直接結束，不煞車
    }

    int s2 = analogRead(S2); int s3 = analogRead(S3); int s4 = analogRead(S4);
    double sum = s1 + s2 + s3 + s4 + s5 + 1;
    double e = (-2.0 * s1 + -1.0 * s2 + 0.0 * s3 + 1.0 * s4 + 2.0 * s5) / sum;
    double pCorr = Kp * e + Kd * (e - lastError);
    MotorWriting(Tp + pCorr, Tp - pCorr);
    lastError = e;

    if (millis() - t > 3000) return;
  }
}

void turnLeft90() {
  lastError=0;  
  int sig=0;
  while (true){
    checkSerialAndFillQueue();
    MotorWriting(20,120);
    if (sig==0){
      if (analogRead(S3)<mid) sig=1;
      }
    if (sig==1){
      if (analogRead(S3)>mid){
        return;
      }
    }
  }
}

void turnRight90() {
 lastError=0;  
  int sig=0;
  while (true){
    checkSerialAndFillQueue();
    MotorWriting(120,20);
    if (sig==0){
      if (analogRead(S3)<mid) sig=1;
      }
    if (sig==1){
      if (analogRead(S3)>mid){
        
        return;
      }
    }
  }
}

void turnAround() {
  lastError=0;
  MotorWriting(130,130);
  delay(280);
  MotorWriting(0,0);
  delay(100);
  MotorWriting(130, -130); delay(400);
  while (analogRead(S4) < mid) {
    checkSerialAndFillQueue();
    MotorWriting(80, -80); scanRFID();
  }
  MotorWriting(0, 0); // 迴轉完停穩
}


// =====================
// 主迴圈 (記憶體總管)
// =====================
void loop() {
  scanRFID();
  checkSerialAndFillQueue();
  // 2. 如果車子有空，且佇列裡有指令，就拿出第一個來執行
  if (cmdQueue.length() > 0) {
    digitalWrite(13, HIGH);
    
    char currentCmd = cmdQueue[0];    // 讀取第一個指令
    cmdQueue.remove(0, 1);            // 把它從記憶體中刪掉 (Pop)

    // 執行對應的動作
    if (currentCmd == 'W') {
      moveOneNode();
      }
    else if (currentCmd == 'A') turnLeft90();
    else if (currentCmd == 'D') turnRight90();
    else if (currentCmd == 'S') {
      turnAround();
    }

    // ⭐ 3. 動作「徹底完成」後，統一回報 K 給電腦，請電腦補貨
    Serial3.print('K');
    digitalWrite(13, LOW);
  }
  checkSerialAndFillQueue();
  if (cmdQueue.length() == 0) {
      MotorWriting(0, 0); 
    }
}