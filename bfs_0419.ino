#include <SPI.h>
#include <MFRC522.h>

// --- 硬體腳位與參數 ---
#define S1 A3
#define S2 A4
#define S3 A5
#define S4 A6
#define S5 A7
int PWMA = 10, AIN2 = 6, AIN1 = 7, BIN1 = 8, BIN2 = 9, PWMB = 11;

int Tp = 140; 
double Kp = 40, Kd = 60, lastError = 0; 
int mid = 60; // 降低門檻讓循線更穩定

#define RST_PIN 49
#define SS_PIN 53
MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(9600); 
  Serial3.begin(9600); // 藍牙
  pinMode(13, OUTPUT); // 診斷燈
  
  pinMode(S1, INPUT); pinMode(S2, INPUT); pinMode(S3, INPUT); 
  pinMode(S4, INPUT); pinMode(S5, INPUT);
  pinMode(PWMA, OUTPUT); pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT);
  pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT); pinMode(PWMB, OUTPUT);
  
  SPI.begin(); mfrc522.PCD_Init();
  
  // 開機閃爍 3 下，確定大腦活著
  for(int i=0; i<3; i++){ digitalWrite(13, HIGH); delay(100); digitalWrite(13, LOW); delay(100); }
}

void MotorWriting(int vL, int vR) {
  if (vL >= 0) { digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW); analogWrite(PWMA, min(vL, 255)); }
  else { digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH); analogWrite(PWMA, min(-vL, 255)); }
  if (vR >= 0) { digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW); analogWrite(PWMB, min(vR, 255)); }
  else { digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH); analogWrite(PWMB, min(-vR, 255)); }
}

void moveOneNode() {
  MotorWriting(Tp, Tp); 
  delay(500); // 強制盲衝，逃離目前的十字路口
  unsigned long startTime = millis();
  while (true) {
    int v1 = analogRead(S1), v5 = analogRead(S5);
    if (v1 >= mid && v5 >= mid) { 
      MotorWriting(80, 80); delay(600); MotorWriting(0,0); break; 
    }
    int s2=(analogRead(S2)>=mid), s3=(analogRead(S3)>=mid), s4=(analogRead(S4)>=mid);
    double error = (v1>=mid)*-2 + s2*-1 + s3*0 + s4*1 + (v5>=mid)*2;
    double pCorr = Kp * error + Kd * (error - lastError);
    MotorWriting(Tp + pCorr, Tp - pCorr); lastError = error;
    if (millis() - startTime > 6000) { MotorWriting(0,0); break; } // 安全跳出
  }
}

void turnLeft90() { MotorWriting(-120, 120); delay(500); while(analogRead(S3)<mid){MotorWriting(-80,80);} MotorWriting(100,-100); delay(60); MotorWriting(0,0); }
void turnRight90() { MotorWriting(120, -120); delay(500); while(analogRead(S3)<mid){MotorWriting(80,-80);} MotorWriting(-100,100); delay(60); MotorWriting(0,0); }
void turnAround() { MotorWriting(130, -130); delay(700); while(analogRead(S3)<mid){MotorWriting(80,-80);} MotorWriting(-100,100); delay(60); MotorWriting(0,0); }

void loop() {
  if (Serial3.available() > 0) {
    char cmd = Serial3.read();
    if (cmd == 'W' || cmd == 'A' || cmd == 'D' || cmd == 'S') {
      digitalWrite(13, HIGH); // 收到指令亮燈
      
      if (cmd == 'W') moveOneNode();
      else if (cmd == 'A') turnLeft90();
      else if (cmd == 'D') turnRight90();
      else if (cmd == 'S') turnAround();
      
      delay(200);
      
      // RFID 處理
      if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
        String uid = "";
        for (byte i = 0; i < mfrc522.uid.size; i++) {
          if (mfrc522.uid.uidByte[i] < 0x10) uid += "0";
          uid += String(mfrc522.uid.uidByte[i], HEX);
        }
        uid.toUpperCase(); // 🌟 修正處：單獨執行，不放在 print 裡
        Serial3.print("UID:"); Serial3.print(uid); Serial3.print(",");
        mfrc522.PICC_HaltA(); mfrc522.PCD_StopCrypto1();
      }

      // 🌟 清空雜訊並回報 K
      while(Serial3.available() > 0) Serial3.read(); 
      Serial3.print('K'); 
      digitalWrite(13, LOW); // 任務完成熄燈
    }
  }
}