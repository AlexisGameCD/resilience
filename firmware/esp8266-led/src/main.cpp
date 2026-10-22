/*
 * RESILIENCE-ALPHA : objet connecte ESP8266 pilotant une LED bicolore (rouge / vert).
 *
 * Il se connecte en WiFi au point d'acces de la solution, interroge led-service
 * (GET /state) et reproduit l'etat courant :
 *   off          : eteinte
 *   green_blink  : vert clignotant (identite reconnue, saisie du mot de passe)
 *   green_on     : vert fixe (acces accorde, 30 s)
 *   red_blink    : rouge clignotant (mot de passe refuse, ~10 fois)
 *   red_on       : rouge fixe (visage non reconnu, 30 s)
 *
 * Les durees (30 s, 10 clignotements) sont gerees cote serveur : l'objet ne fait
 * qu'afficher l'etat renvoye, ce qui le garde simple et sans etat.
 *
 * Cablage (LED bicolore 3 broches, cathode commune) :
 *   anode VERTE  -> resistance 220-330 ohm -> D1 (GPIO5)
 *   anode ROUGE  -> resistance 220-330 ohm -> D2 (GPIO4)
 *   cathode commune                        -> GND
 */
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

#ifndef WIFI_SSID
#define WIFI_SSID "RESILIENCE-G3"
#endif
#ifndef WIFI_PASS
#define WIFI_PASS "changeme"
#endif
#ifndef LED_SERVICE_URL
#define LED_SERVICE_URL "http://192.168.137.1:8085/state"
#endif

const int GREEN_PIN = D1;              // GPIO5
const int RED_PIN   = D2;              // GPIO4
const unsigned long POLL_INTERVAL = 300;   // ms entre deux interrogations
const unsigned long BLINK_PERIOD  = 500;   // ms (demi-periode de clignotement)

String currentDisplay = "off";
unsigned long lastPoll = 0, lastBlink = 0;
bool blinkOn = false;

void applyDisplay() {
  bool g = false, r = false;
  if (currentDisplay == "green_on")         g = true;
  else if (currentDisplay == "red_on")      r = true;
  else if (currentDisplay == "green_blink") g = blinkOn;
  else if (currentDisplay == "red_blink")   r = blinkOn;
  digitalWrite(GREEN_PIN, g ? HIGH : LOW);
  digitalWrite(RED_PIN,   r ? HIGH : LOW);
}

void pollState() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClient client;
  HTTPClient http;
  if (http.begin(client, LED_SERVICE_URL)) {
    int code = http.GET();
    if (code == 200) {
      String payload = http.getString();
      JsonDocument doc;
      if (!deserializeJson(doc, payload)) {
        currentDisplay = String((const char*)(doc["display"] | "off"));
      }
    }
    http.end();
  }
}

void setup() {
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(RED_PIN, OUTPUT);
  digitalWrite(GREEN_PIN, LOW);
  digitalWrite(RED_PIN, LOW);

  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connexion au point d'acces ");
  Serial.print(WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) { delay(400); Serial.print("."); }
  Serial.println();
  Serial.print("Connecte, IP : ");
  Serial.println(WiFi.localIP());
  Serial.print("led-service : ");
  Serial.println(LED_SERVICE_URL);
}

void loop() {
  unsigned long now = millis();
  if (now - lastPoll >= POLL_INTERVAL)  { lastPoll = now;  pollState(); }
  if (now - lastBlink >= BLINK_PERIOD)  { lastBlink = now; blinkOn = !blinkOn; }
  applyDisplay();
  delay(10);
}
