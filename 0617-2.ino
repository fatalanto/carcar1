#include <Servo.h> //伺服馬達函式庫

//超音波感測器
const int EtrigPin = A2;
const int EechoPin = 2;
long durationE;
int distanceE;

const int FtrigPin = A5;
const int FechoPin = 13;
long durationF;
int distanceF;

//藍色TT馬達腳位
//左輪
const int AIN1 = 4;
const int AIN2 = 3;
const int PWMA = 5;

//右輪
const int BIN1 = 6;
const int BIN2 = 7;
const int PWMB = 8;

//微型馬達
//左側微型馬達
const int CIN1 = A0;
const int CIN2 = A1;
const int PWMC = 11;

//右側微型馬達
const int DIN1 = A3;
const int DIN2 = A4;
const int PWMD = 12;

//速度設定
const int ttSpeed1 = 130;
const int ttSpeed2 = 125;
const int ttSpeed3 = 0;
const int microSpeed = 150;
const int legSpeed = 210;

//伺服馬達腳位
const int servo1Pin = 9;
const int servo2Pin = 10;

Servo myServo1;
Servo myServo2;


int targetSide = 0;//0未決定，1往 E 邊走，2往 F 邊走

void turnLeft() {

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);
delay(1000);

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

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

void turnRight() {

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);
delay(1000);
digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, 100);

digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, 100);

digitalWrite(CIN1, LOW); digitalWrite(CIN2, HIGH); analogWrite(PWMC, microSpeed);
digitalWrite(DIN1, LOW); digitalWrite(DIN2, HIGH); analogWrite(PWMD, microSpeed);
syncSlowMove(myServo1, 105, myServo2, 75, 15);

}

//慢速轉動
void syncSlowMove(Servo &motor1, int target1, Servo &motor2, int target2, int speedDelay) {
int pos1 = motor1.read();
int pos2 = motor2.read();

while (pos1 != target1 || pos2 != target2) {

if (pos1 < target1) {
pos1++;
} else if (pos1 > target1) {
pos1--;
}

if (pos2 < target2) {
pos2++;
} else if (pos2 > target2) {
pos2--;
}

motor1.write(pos1);
motor2.write(pos2);

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
}

void loop() {

  //測量超音波E
  digitalWrite(EtrigPin, LOW);        delayMicroseconds(2);
  digitalWrite(EtrigPin, HIGH);       delayMicroseconds(10);
  digitalWrite(EtrigPin, LOW);
  durationE = pulseIn(EechoPin, HIGH);
  distanceE = durationE * 0.034 / 2;
  delay(20); 

  //測量超音波F
  digitalWrite(FtrigPin, LOW);        delayMicroseconds(2);
  digitalWrite(FtrigPin, HIGH);       delayMicroseconds(10);
  digitalWrite(FtrigPin, LOW);
  durationF = pulseIn(FechoPin, HIGH);
  distanceF = durationF * 0.034 / 2;

  Serial.print("DistanceE:");  Serial.println(distanceE);
  Serial.print("DistanceF:");  Serial.println(distanceF);
  delay(30); 
  
  //如果目前沒有鎖定目標選長的那邊鎖定
  if (targetSide == 0) {
    if (distanceE > distanceF) {
      targetSide = 1; // 鎖定往 E 邊前進
      Serial.println("往 E 邊前進");
    } else {
      targetSide = 2; // 鎖定往 F 邊前進
      Serial.println("往 F 邊前進");
    }
  }

  if (targetSide == 1) {
    if (distanceE > 25) {
      turnRight(); 
    } 
    else {
      syncSlowMove(myServo1, 135, myServo2, 45, 30);      
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, HIGH); analogWrite(PWMA, 40);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, HIGH); analogWrite(PWMB, 40);
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, LOW);  analogWrite(PWMC, 0); 
      digitalWrite(DIN1, LOW);  digitalWrite(DIN2, LOW);  analogWrite(PWMD, 0); 
      delay(500);
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, LOW);  analogWrite(PWMA, 0);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, LOW);  analogWrite(PWMB, 0);
      delay(3000); //等3秒
      
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, HIGH); analogWrite(PWMC, 40);
      digitalWrite(DIN1, HIGH); digitalWrite(DIN2, LOW);  analogWrite(PWMD, 40);
      delay(500);
      
      Serial.println("抵達 E 牆壁、Action()");
      Action(); 
      
      targetSide = 0;//解鎖
    }
  } 
  else if (targetSide == 2) {
    if (distanceF > 25) {
      turnLeft(); 
    } 
    else {
      syncSlowMove(myServo1, 135, myServo2, 45, 30);      
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, HIGH); analogWrite(PWMA, 40);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, HIGH); analogWrite(PWMB, 40);
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, LOW);  analogWrite(PWMC, 0); 
      digitalWrite(DIN1, LOW);  digitalWrite(DIN2, LOW);  analogWrite(PWMD, 0); 
      delay(1000);
      
      digitalWrite(AIN1, LOW);  digitalWrite(AIN2, LOW);  analogWrite(PWMA, 0);
      digitalWrite(BIN1, LOW);  digitalWrite(BIN2, LOW);  analogWrite(PWMB, 0);
      delay(8000); //等3秒
      
      digitalWrite(CIN1, LOW);  digitalWrite(CIN2, HIGH); analogWrite(PWMC, 40);
      digitalWrite(DIN1, HIGH); digitalWrite(DIN2, LOW);  analogWrite(PWMD, 40);
      delay(500);
      
      Serial.println("抵達 F 牆壁、Action()");
      Action(); 
      
      targetSide = 0;
    }
  }
  delay(50); 
}

//爬樓梯動作
void Action() {
digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, ttSpeed1);

digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, ttSpeed1);
delay(500);

digitalWrite(AIN1, HIGH);
digitalWrite(AIN2, LOW);
analogWrite(PWMA, ttSpeed2);

digitalWrite(BIN1, HIGH);
digitalWrite(BIN2, LOW);
analogWrite(PWMB, ttSpeed2);

digitalWrite(CIN1, HIGH);
digitalWrite(CIN2, LOW);
analogWrite(PWMC, microSpeed);

digitalWrite(DIN1, LOW);
digitalWrite(DIN2, HIGH);
analogWrite(PWMD, microSpeed);
syncSlowMove(myServo1, 45, myServo2, 135, 10);
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
