#include <Servo.h> // 引入伺服馬達函式庫
 // 引入強大的超音波函式庫

// --- 超音波感測器 ---
const int EtrigPin = A2; // 改用 A2
const int EechoPin = 2;
long durationE;
int distanceE;

const int FtrigPin = A5; // 改用 A5
const int FechoPin = 13; // 改用 13
long durationF;
int distanceF;

// --- 藍色TT馬達腳位定義 ---
// 左輪 (A 通道)
const int AIN1 = 4;
const int AIN2 = 3;
const int PWMA = 5;

// 右輪 (B 通道)
const int BIN1 = 6;
const int BIN2 = 7;
const int PWMB = 8;

// --- 第二組驅動板：微型馬達 (裝輪子) ---
// 左側微型馬達 (C 通道)
const int CIN1 = A0;
const int CIN2 = A1;
const int PWMC = 11;

// 右側微型馬達 (D 通道)
const int DIN1 = A3;
const int DIN2 = A4;
const int PWMD = 12;

// 安全速度設定 (配合 11.1V 電池推 6V 馬達)
const int ttSpeed1 = 130;
const int ttSpeed2 = 125;
const int ttSpeed3 = 0;
const int microSpeed = 150;
const int legSpeed = 210;

// --- 伺服馬達腳位定義與物件建立 ---
const int servo1Pin = 9;
const int servo2Pin = 10;

Servo myServo1; // 建立伺服馬達 1 的物件
Servo myServo2; // 建立伺服馬達 2 的物件

// 記錄馬達目前的位置，假設一開始在 0 度
// ==========================================
// 🌟 新增：全域變數，用來記憶鎖定的方向
// 0 = 未決定, 1 = 鎖定往 E 邊走, 2 = 鎖定往 F 邊走
// ==========================================
int targetSide = 0;

void turnLeft() {

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);
delay(1000);

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);

digitalWrite(CIN1, HIGH);
digitalWrite(CIN2, LOW);
analogWrite(PWMC, microSpeed);

digitalWrite(DIN1, HIGH);
digitalWrite(DIN2, LOW);
analogWrite(PWMD, microSpeed);
syncSlowMove(myServo1, 105, myServo2, 75, 15);
}

// 4. 🌟 新增：往右轉 (TT馬達停止，只有微型馬達動)
void turnRight() {

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);
delay(1000);
digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);

// 微型馬達作動：左邊微型前進，右邊微型後退
digitalWrite(CIN1, LOW); digitalWrite(CIN2, HIGH); analogWrite(PWMC, microSpeed);
digitalWrite(DIN1, LOW); digitalWrite(DIN2, HIGH); analogWrite(PWMD, microSpeed);
syncSlowMove(myServo1, 105, myServo2, 75, 15);

}


// ==========================================
// 🌟 這是自訂的「慢速轉動」函式，請把它放在程式的最下方
// ==========================================
void syncSlowMove(Servo &motor1, int target1, Servo &motor2, int target2, int speedDelay) {
// 讀取兩顆馬達目前所在的真實角度
int pos1 = motor1.read();
int pos2 = motor2.read();

// 只要「其中一顆」馬達還沒到達目標，迴圈就會繼續執行
while (pos1 != target1 || pos2 != target2) {

// --- 計算馬達 1 下一步該往哪走 ---
if (pos1 < target1) {
pos1++; // 還沒到，加 1 度
} else if (pos1 > target1) {
pos1--; // 超過了，減 1 度
}

// --- 計算馬達 2 下一步該往哪走 ---
if (pos2 < target2) {
pos2++;
} else if (pos2 > target2) {
pos2--;
}

// --- 同時對兩顆馬達下達新角度 ---
motor1.write(pos1);
motor2.write(pos2);

// --- 兩顆馬達一起等待一小段時間 (決定速度) ---
delay(speedDelay);
}
}



void setup() {
pinMode(EtrigPin, OUTPUT);
pinMode(EechoPin, INPUT);
pinMode(FtrigPin, OUTPUT);
pinMode(FechoPin, INPUT);
Serial.begin(9600);

// 設定 TT 馬達腳位為輸出
pinMode(AIN1, OUTPUT);
pinMode(AIN2, OUTPUT);
pinMode(PWMA, OUTPUT);

pinMode(BIN1, OUTPUT);
pinMode(BIN2, OUTPUT);
pinMode(PWMB, OUTPUT);

// 設定微型馬達腳位為輸出
pinMode(CIN1, OUTPUT);
pinMode(CIN2, OUTPUT);
pinMode(PWMC, OUTPUT);

pinMode(DIN1, OUTPUT);
pinMode(DIN2, OUTPUT);
pinMode(PWMD, OUTPUT);

// 初始化伺服馬達
myServo1.attach(servo1Pin);
myServo2.attach(servo2Pin);
myServo1.write(135);
myServo2.write(45);

syncSlowMove(myServo1, 135, myServo2, 45, 30);
delay(1000);

// 讓伺服馬達先回到 90 度的初始位置

}

void loop() {

  // --- 分開測量第一顆超音波 (E) ---
  digitalWrite(EtrigPin, LOW);        delayMicroseconds(2);
  digitalWrite(EtrigPin, HIGH);       delayMicroseconds(10);
  digitalWrite(EtrigPin, LOW);
  durationE = pulseIn(EechoPin, HIGH);
  distanceE = durationE * 0.034 / 2;
  delay(20); 

  // --- 分開測量第二顆超音波 (F) ---
  digitalWrite(FtrigPin, LOW);        delayMicroseconds(2);
  digitalWrite(FtrigPin, HIGH);       delayMicroseconds(10);
  digitalWrite(FtrigPin, LOW);
  durationF = pulseIn(FechoPin, HIGH);
  distanceF = durationF * 0.034 / 2;

  // --- 輸出結果 ---
  Serial.print("DistanceE:");  Serial.println(distanceE);
  Serial.print("DistanceF:");  Serial.println(distanceF);
  delay(30); 

  // ==========================================
  // 🌟 核心：記憶鎖定邏輯
  // ==========================================
  
  // 步驟 1：如果目前沒有鎖定目標，就比大小，選長的那邊鎖定
  if (targetSide == 0) {
    if (distanceE > distanceF) {
      targetSide = 1; // 鎖定往 E 邊前進
      Serial.println("🎯 目標鎖定：往 E 邊前進");
    } else {
      targetSide = 2; // 鎖定往 F 邊前進
      Serial.println("🎯 目標鎖定：往 F 邊前進");
    }
  }

  // 步驟 2：根據鎖定的目標，一路走到底，直到接近牆壁
  if (targetSide == 1) {
    // 執行鎖定 E 的任務
    if (distanceE > 25) {
      turnRight(); 
    } 
    else {
      // 終於接近 E 牆壁了！執行前置動作
      syncSlowMove(myServo1, 135, myServo2, 45, 30);      
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, HIGH); analogWrite(PWMA, 40);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, HIGH); analogWrite(PWMB, 40);
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, LOW);  analogWrite(PWMC, 0); 
      digitalWrite(DIN1, LOW);  digitalWrite(DIN2, LOW);  analogWrite(PWMD, 0); 
      delay(500); // 後退 0.5 秒
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, LOW);  analogWrite(PWMA, 0);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, LOW);  analogWrite(PWMB, 0);
      delay(3000); // 靜止等待 3 秒
      
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, HIGH); analogWrite(PWMC, 40);
      digitalWrite(DIN1, HIGH); digitalWrite(DIN2, LOW);  analogWrite(PWMD, 40);
      delay(500);
      
      Serial.println("⚠️ 抵達 E 牆壁！觸發 Action()！");
      Action(); 
      
      targetSide = 0; // 大招放完後解鎖目標，下一輪重新選路
    }
  } 
  else if (targetSide == 2) {
    // 執行鎖定 F 的任務
    if (distanceF > 25) {
      turnLeft(); 
    } 
    else {
      // 終於接近 F 牆壁了！執行前置動作
      syncSlowMove(myServo1, 135, myServo2, 45, 30);      
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, HIGH); analogWrite(PWMA, 40);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, HIGH); analogWrite(PWMB, 40);
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, LOW);  analogWrite(PWMC, 0); 
      digitalWrite(DIN1, LOW);  digitalWrite(DIN2, LOW);  analogWrite(PWMD, 0); 
      delay(1000); // 後退 1 秒
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, LOW);  analogWrite(PWMA, 0);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, LOW);  analogWrite(PWMB, 0);
      delay(8000); // 靜止等待 3 秒
      
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, HIGH); analogWrite(PWMC, 40);
      digitalWrite(DIN1, HIGH); digitalWrite(DIN2, LOW);  analogWrite(PWMD, 40);
      delay(500);
      
      Serial.println("⚠️ 抵達 F 牆壁！觸發 Action()！");
      Action(); 
      
      targetSide = 0; // 大招放完後解鎖目標，下一輪重新選路
    }
  }

  delay(50); 
}


void Action() {
// --- 動作 1：雙輪前進，伺服馬達轉到 180 度 ---
// 左輪正轉
digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, ttSpeed1);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, ttSpeed1);
delay(500);

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, ttSpeed2);

// 右輪正轉 ( 如果接好發現方向相反，請把HIGH/LOW 互換)
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, ttSpeed2);

digitalWrite(CIN1, HIGH);
digitalWrite(CIN2, LOW);
analogWrite(PWMC, microSpeed);

digitalWrite(DIN1, LOW);
digitalWrite(DIN2, HIGH);
analogWrite(PWMD, microSpeed);
syncSlowMove(myServo1, 45, myServo2, 135, 10);//轉道90
analogWrite(PWMA, 0);
analogWrite(PWMB, 0);
syncSlowMove(myServo1, 15, myServo2, 165, 30);

digitalWrite(CIN1, LOW);
digitalWrite(CIN2, LOW);
analogWrite(PWMC, 0);
digitalWrite(DIN1, LOW);
digitalWrite(DIN2, LOW);
analogWrite(PWMD, 0);


delay(3000);

//收腳
digitalWrite(AIN1, LOW);
digitalWrite(AIN2, HIGH);
analogWrite(PWMA, ttSpeed3);

// 右輪正轉 (如果接好發現方向相反，請把 HIGH/LOW 互換)
digitalWrite(BIN1, LOW);
digitalWrite(BIN2, HIGH);
analogWrite(PWMB, ttSpeed3);


delay(1000);

digitalWrite(AIN1, LOW);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 0);
digitalWrite(BIN1, LOW);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 0);

syncSlowMove(myServo1, 135,myServo2, 165, 15);
digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, legSpeed);
digitalWrite(AIN1, LOW);
digitalWrite(AIN2, HIGH);
analogWrite(PWMA, 100);

delay(3000);

syncSlowMove(myServo1, 135, myServo2, 45, 15);
digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, legSpeed);
digitalWrite(BIN1, LOW);
digitalWrite(BIN2, HIGH);
analogWrite(PWMB, 130);

delay(2000);
digitalWrite(AIN1, LOW);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 0);
digitalWrite(BIN1, LOW);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 0);
delay(10000);
}
