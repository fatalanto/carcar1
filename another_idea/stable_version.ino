#include <SPI.h>
#include <MFRC522.h>

#define S1 A3
#define S2 A4
#define S3 A5
#define S4 A6
#define S5 A7

int PWMA = 10, AIN2 = 6, AIN1 = 7;
int BIN1 = 8, BIN2 = 9, PWMB = 11;

int Tp = 180;
double Kp = 40, Kd = 60, lastError = 0;
int mid = 80;

#define RST_PIN 49
#define SS_PIN 53
MFRC522 mfrc522(SS_PIN, RST_PIN);

String lastUID = "";
unsigned long lastUIDTime = 0;

String cmdQueue = "";
char lastCommand = 'W';

void setup() {
  Serial.begin(9600);
  Serial3.begin(9600);

  pinMode(13, OUTPUT);

  pinMode(S1, INPUT); pinMode(S2, INPUT); pinMode(S3, INPUT);
  pinMode(S4, INPUT); pinMode(S5, INPUT);

  pinMode(PWMA, OUTPUT); pinMode(AIN1, OUTPUT); pinMode(AIN2, OUTPUT);
  pinMode(PWMB, OUTPUT); pinMode(BIN1, OUTPUT); pinMode(BIN2, OUTPUT);

  SPI.begin();
  mfrc522.PCD_Init();

  for (int i = 0; i < 3; i++) {
    digitalWrite(13, HIGH); delay(100);
    digitalWrite(13, LOW); delay(100);
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

  if (uid == lastUID && millis() - lastUIDTime < 1500) return;

  lastUID = uid;
  lastUIDTime = millis();
  Serial3.print("UID:" + uid + ",");
}

void MotorWriting(int vL, int vR) {
  if (vL >= 0) {
    digitalWrite(AIN1, HIGH); digitalWrite(AIN2, LOW);
    analogWrite(PWMA, constrain(vL, 0, 255));
  } else {
    digitalWrite(AIN1, LOW); digitalWrite(AIN2, HIGH);
    analogWrite(PWMA, constrain(-vL, 0, 255));
  }

  if (vR >= 0) {
    digitalWrite(BIN1, HIGH); digitalWrite(BIN2, LOW);
    analogWrite(PWMB, constrain(vR, 0, 255));
  } else {
    digitalWrite(BIN1, LOW); digitalWrite(BIN2, HIGH);
    analogWrite(PWMB, constrain(-vR, 0, 255));
  }
}

void checkSerialAndFillQueue() {
  while (Serial3.available() && cmdQueue.length() < 3) {
    char c = Serial3.read();
    if (c == 'W' || c == 'A' || c == 'D' || c == 'S') {
      cmdQueue += c;
    }
  }
}

void moveOneNode() {
  MotorWriting(100, 100);
  delay(40);

  unsigned long t = millis();
  unsigned long startUIDTime = lastUIDTime;
  unsigned long blindTime = (lastCommand == 'W') ? 500 : 0;

  while (true) {
    scanRFID();
    checkSerialAndFillQueue();

    if (lastUIDTime != startUIDTime) {
      MotorWriting(0, 0);
      delay(40);
      lastError = 0;
      return;
    }

    int s1 = analogRead(S1);
    int s5 = analogRead(S5);

    if (millis() - t >= blindTime) {
      if (s1 >= mid && s5 >= mid) {
        lastError = 0;
        return;
      }
    }

    int s2 = analogRead(S2);
    int s3 = analogRead(S3);
    int s4 = analogRead(S4);

    double sum = s1 + s2 + s3 + s4 + s5 + 1;
    double e = (-2.0 * s1 + -1.0 * s2 + 0.0 * s3 + 1.0 * s4 + 2.0 * s5) / sum;

    double pCorr = Kp * e + Kd * (e - lastError);
    MotorWriting(Tp + pCorr, Tp - pCorr);
    lastError = e;

    if (millis() - t > 3000) return;
  }
}

void turnLeft90() {
  lastError = 0;
  int sig = 0;

  while (true) {
    checkSerialAndFillQueue();
    MotorWriting(20, 120);

    if (sig == 0 && analogRead(S3) < mid) sig = 1;
    if (sig == 1 && analogRead(S3) > mid) return;
  }
}

void turnRight90() {
  lastError = 0;
  int sig = 0;

  while (true) {
    checkSerialAndFillQueue();
    MotorWriting(120, 20);

    if (sig == 0 && analogRead(S3) < mid) sig = 1;
    if (sig == 1 && analogRead(S3) > mid) return;
  }
}

void turnAround() {
  lastError = 0;
  MotorWriting(130, -130);
  delay(450);

  while (analogRead(S4) < mid) {
    checkSerialAndFillQueue();
    MotorWriting(60, -60);
    scanRFID();
  }

  MotorWriting(0, 0);
}

void loop() {
  scanRFID();
  checkSerialAndFillQueue();

  if (cmdQueue.length() > 0) {
    digitalWrite(13, HIGH);

    char currentCmd = cmdQueue[0];
    cmdQueue.remove(0, 1);

    if (currentCmd == 'W') moveOneNode();
    else if (currentCmd == 'A') turnLeft90();
    else if (currentCmd == 'D') turnRight90();
    else if (currentCmd == 'S') turnAround();

    lastCommand = currentCmd;
    Serial3.print('K');

    digitalWrite(13, LOW);
  }

  if (cmdQueue.length() == 0) {
    MotorWriting(0, 0);
  }
}
