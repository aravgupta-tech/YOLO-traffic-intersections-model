#include <Wire.h>
#include <LiquidCrystal_I2C.h>


LiquidCrystal_I2C lcd(0x27, 16, 2);


// ===== CONFIG (change your variables here) =====
const int redPins[4]   = {2, 7, 9, 12};
const int greenPins[4] = {4, 8, 10, 13};
int activeRoads = 0;
unsigned long greenTime = 0;
unsigned long counts[4] = {0,0,0,0};


// Custom characters: traffic light and pole (animation on lcd screen, remove if you do not have one)
byte trafficLight[8] = {
  B00100,
  B01110,
  B01110,
  B01110,
  B01110,
  B01110,
  B01110,
  B00100
};


byte pole[8] = {
  B00100,
  B00100,
  B00100,
  B00100,
  B00100,
  B00100,
  B00100,
  B00100
};


// ===== LCD WIPE ANIMATION (remove if not using lcd) =====
void lcdWipe(String msg) {
  lcd.clear();
  for (int i = 0; i <= msg.length(); i++) {
    lcd.setCursor(0, 0);
    lcd.print(msg.substring(0, i));
    delay(60);
  }
}

void showProgress() {
  const char* messages[] = {
    "Initializing...",
    "Mainframing...",
    "Loading YOLO...",
    "System Arming..."
  };


  int numMessages = 4;
  int progress = 0;


  for (int i = 0; i < numMessages; i++) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(messages[i]);


    int endVal = (i + 1) * 25;
    int duration = random(2000, 4000);  // scale for 12.5s total, depending on preference you can change time
    unsigned long start = millis();


    while (millis() - start < duration) {
      progress = map(millis() - start, 0, duration, i * 25, endVal);
      int bars = map(progress, 0, 100, 0, 10);


      lcd.setCursor(0, 1);
      lcd.print("[");
      for (int b = 0; b < 10; b++) {
        if (b < bars) lcd.print("#");
        else lcd.print(" ");
      }
      lcd.print("]");
      lcd.print(progress);
      lcd.print("%");


      delay(random(150, 350)); // uneven progression for realism
    }
  }
}


// ===== ACTUAL SETUP =====
void setup() {
  Serial.begin(9600);
  lcd.init();
  lcd.backlight();


  for (int i = 0; i < 4; i++) {
    pinMode(redPins[i], OUTPUT);
    pinMode(greenPins[i], OUTPUT);
    digitalWrite(redPins[i], HIGH);
    digitalWrite(greenPins[i], LOW);
  }


  lcd.createChar(0, trafficLight);
  lcd.createChar(1, pole);


  // === Boot sequence (for looks) ===
  lcd.clear();
  delay(1000); // 0–1s blank


  // 1–3s FlowSense v1.7 animated dots (animation again for looks)
  unsigned long start = millis();
  while (millis() - start < 2000) {
    lcd.setCursor(0, 0);
    lcd.print("FlowSense v1.7"); // change to your own name
    lcd.setCursor(0, 1);
    int stage = ((millis() - start) / 400) % 3; // cycles 1–3 dots (typing animation)
    for (int i = 0; i <= stage; i++) lcd.print(".");
    delay(200);
    lcd.setCursor(0, 1);
    lcd.print("                ");
  }

  for (int i = 0; i < 16; i++) {
    lcd.setCursor(i, 0);
    lcd.print(" ");
    delay(25);
  }
  lcd.clear();
  delay(100);

  showProgress();
  lcd.clear();
}


// ===== MAIN LOOP =====
void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();


    if (data.length() > 0 && data.indexOf(';') != -1) {
      int sep = data.indexOf(';');
      String nums = data.substring(0, sep);
      activeRoads = data.substring(sep + 1).toInt();


      for (int i = 0; i < 4; i++) counts[i] = 0;


      int i = 0;
      int last = 0;
      for (int j = 0; j < nums.length(); j++) {
        if (nums[j] == ',') {
          counts[i++] = nums.substring(last, j).toInt();
          last = j + 1;
        }
      }
      counts[i] = nums.substring(last).toInt();
    }
  }

  for (int i = 0; i < activeRoads; i++) {
    greenTime = counts[i];

    String msg = " Road " + String(i+1) + " GREEN";
    lcd.setCursor(0, 0);
    lcd.write(byte(0));
    for (int c = 0; c < msg.length(); c++) {
      lcd.setCursor(c + 1, 0);
      lcd.print(msg[c]);
      delay(20);
    }


    digitalWrite(redPins[i], LOW);
    digitalWrite(greenPins[i], HIGH);


    for (int j = 0; j < 4; j++) {
      if (j != i) {
        digitalWrite(redPins[j], HIGH);
        digitalWrite(greenPins[j], LOW);
      }
    }


    unsigned long startMillis = millis();
    while (millis() - startMillis < greenTime) {
      unsigned long elapsed = millis() - startMillis;
      unsigned long remaining = (greenTime > elapsed) ? greenTime - elapsed : 0;


      lcd.setCursor(0, 1);
      lcd.write(byte(1)); // pole (part of design change if not using lcd)
      lcd.print(" Time: ");
      lcd.print(remaining / 1000);
      lcd.print("s   ");


      delay(200);
    }


    digitalWrite(greenPins[i], LOW);
    digitalWrite(redPins[i], HIGH);
  }
}
