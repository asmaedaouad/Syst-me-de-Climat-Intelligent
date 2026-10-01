#include "DHT.h"
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <time.h>
#include "Adafruit_MQTT.h"
#include "Adafruit_MQTT_Client.h"
#include "secrets.h"   // copier secrets.h.example -> secrets.h

// Configuration WiFi
const char* ssid = WIFI_SSID;     
const char* password = WIFI_PASSWORD;        

// URL de  Node-RED
const char* serverUrl = NODERED_URL;

// Configuration Adafruit IO
#define AIO_SERVER      "io.adafruit.com"
#define AIO_SERVERPORT  1883
#define AIO_USERNAME    SECRET_AIO_USERNAME
#define AIO_KEY         SECRET_AIO_KEY

// Pins
#define DHTPIN D2
#define DHTTYPE DHT22
#define LED_ROUGE D3    // LED Rouge pour chauffage
#define LED_BLEUE D4    // LED Bleue pour ventilateur/climatisation

DHT dht(DHTPIN, DHTTYPE);

bool wifiConnected = false;

// Variables pour Adafruit MQTT
WiFiClient client;
Adafruit_MQTT_Client mqtt(&client, AIO_SERVER, AIO_SERVERPORT, AIO_USERNAME, AIO_KEY);

// Déclaration des feeds Adafruit IO
Adafruit_MQTT_Publish temperatureFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/temperature");
Adafruit_MQTT_Publish heaterLevelFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/heater-level");
Adafruit_MQTT_Publish fanLevelFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/fan-level");
Adafruit_MQTT_Publish locationFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/location");
Adafruit_MQTT_Publish chaufageFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/chaufage");
Adafruit_MQTT_Publish ventilataireFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/ventilataire");

// Feed pour l'image
Adafruit_MQTT_Publish imageFeed = Adafruit_MQTT_Publish(&mqtt, AIO_USERNAME "/feeds/image");

// Feeds pour la réception des commandes
Adafruit_MQTT_Subscribe chaufageControl = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "/feeds/chaufage");
Adafruit_MQTT_Subscribe ventilataireControl = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "/feeds/ventilataire");
Adafruit_MQTT_Subscribe manualModeControl = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "/feeds/manualmode");
Adafruit_MQTT_Subscribe heaterLevelControl = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "/feeds/heater-level");
Adafruit_MQTT_Subscribe fanLevelControl = Adafruit_MQTT_Subscribe(&mqtt, AIO_USERNAME "/feeds/fan-level");

// Variables pour le contrôle des LEDs
int currentHeaterLevel = 0;
int currentFanLevel = 0;
unsigned long lastLEDUpdate = 0;
bool ledState = false;
bool manualHeaterControl = false;
bool manualFanControl = false;
bool manualMode = false;

// Variables pour la localisation
const char* locationName = "Al Hoceima, Maroc";
const float LOCATION_LAT = 35.2517;
const float LOCATION_LON = -3.9372;

// URL de l'image hébergée sur Imgur
const char* imageUrl = "https://i.imgur.com/6VjJRV.jpeg";

bool locationPublished = false;
bool imagePublished = false;

unsigned long lastLocationUpdate = 0;
const unsigned long LOCATION_UPDATE_INTERVAL = 300000; // 5 minutes


unsigned long lastAdafruitPublish = 0;
const unsigned long ADAFRUIT_PUBLISH_INTERVAL = 5000; // 5 secondes
bool needsAdafruitUpdate = true; 

void setup() {
  Serial.begin(115200);
  delay(1000);
  dht.begin();

  pinMode(LED_ROUGE, OUTPUT);
  pinMode(LED_BLEUE, OUTPUT);

  // Éteindre les LEDs au démarrage
  digitalWrite(LED_ROUGE, LOW);
  digitalWrite(LED_BLEUE, LOW);

  Serial.println("\n");
  Serial.println("========================================");
  Serial.println("  SYSTEME DE CONTROLE CLIMATIQUE");
  Serial.println("  DHT22 + Adafruit IO + Node-RED + Azure SQL");
  Serial.println("========================================");

  // Tentative de connexion WiFi
  Serial.print("SSID: ");
  Serial.println(ssid);
  Serial.print("Connexion au WiFi");

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 60) {
    delay(500);
    Serial.print(".");
    attempts++;

    if (attempts % 10 == 0) {
      Serial.print(" [");
      Serial.print(WiFi.status());
      Serial.print("] ");
    }
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[OK] WiFi connecte avec succes");
    Serial.print("     IP Locale    : ");
    Serial.println(WiFi.localIP());
    Serial.print("     Signal (RSSI): ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    wifiConnected = true;

    configTime(3600, 0, "pool.ntp.org");
    Serial.println("     Sync NTP     : En cours...");
    delay(2000);
    Serial.println("     Sync NTP     : OK");
    
    // Configuration Adafruit MQTT
    mqtt.subscribe(&chaufageControl);
    mqtt.subscribe(&ventilataireControl);
    mqtt.subscribe(&manualModeControl);
    mqtt.subscribe(&heaterLevelControl);
    mqtt.subscribe(&fanLevelControl);
    Serial.println("     Adafruit IO  : Configure");
    
  } else {
    Serial.println("\n[ERREUR] Connexion WiFi echouee");
    Serial.println("         Mode LOCAL uniquement");
    wifiConnected = false;
  }

  Serial.println("========================================");
  Serial.println("  SYSTEME PRET - Demarrage monitoring");
  Serial.println("========================================\n");
}

// Fonction de connexion MQTT
void MQTT_connect() {
  if (mqtt.connected()) {
    return;
  }

  Serial.print("Connexion Adafruit IO... ");
  
  int8_t ret;
  uint8_t retries = 3;
  
  while ((ret = mqtt.connect()) != 0) {
    Serial.println(mqtt.connectErrorString(ret));
    Serial.println("Nouvelle tentative dans 5 secondes...");
    mqtt.disconnect();
    delay(5000);
    retries--;
    if (retries == 0) {
      Serial.println("Echec connexion Adafruit IO");
      return;
    }
  }
  
  Serial.println("Adafruit IO connecte!");
}

// Fonction pour publier les informations de localisation
void publishLocationInfo() {
  if (wifiConnected && mqtt.connected()) {
    // Format JSON pour Adafruit IO Map
    String locationData = "{\"value\":1,\"lat\":" + String(LOCATION_LAT, 4) + ",\"lon\":" + String(LOCATION_LON, 4) + "}";
    
    if (locationFeed.publish(locationData.c_str())) {
      Serial.println("========================================");
      Serial.println("INFORMATIONS DE LOCALISATION:");
      Serial.print("  Ville: ");
      Serial.println(locationName);
      Serial.print("  Coordonnees: ");
      Serial.print(LOCATION_LAT, 4);
      Serial.print(", ");
      Serial.println(LOCATION_LON, 4);
      Serial.print("  Format JSON: ");
      Serial.println(locationData);
      Serial.println("  Localisation publiee avec succes!");
      Serial.println("========================================");
      locationPublished = true;
    } else {
      Serial.println("ERREUR: Echec publication localisation");
    }
  }
}

// Fonction pour publier l'image
void publishImageInfo() {
  if (wifiConnected && mqtt.connected() && !imagePublished) {
    if (imageFeed.publish(imageUrl)) {
      Serial.println("========================================");
      Serial.println("URL IMAGE PUBLIEE:");
      Serial.print("  URL: ");
      Serial.println(imageUrl);
      Serial.println("  Image publiee avec succes!");
      Serial.println("========================================");
      imagePublished = true;
    } else {
      Serial.println("ERREUR: Echec publication image");
    }
  }
}

// Déterminer le niveau de 1 à 5 selon la différence de température
int niveauChauffage(float diff) {
  if (diff <= 1.0) return 1;
  else if (diff <= 2.0) return 2;
  else if (diff <= 3.0) return 3;
  else if (diff <= 4.0) return 4;
  else return 5;
}

int niveauVentilateur(float diff) {
  if (diff <= 1.0) return 1;
  else if (diff <= 2.0) return 2;
  else if (diff <= 3.0) return 3;
  else if (diff <= 4.0) return 4;
  else return 5;
}

// Fonction pour contrôler le clignotement des LEDs
void updateLEDs() {
  if (manualMode) {
    // Mode manuel - LEDs contrôlées uniquement par les commandes manuelles
    if (manualHeaterControl && currentHeaterLevel > 0) {
      digitalWrite(LED_ROUGE, HIGH); // Allumé en continu en mode manuel
      digitalWrite(LED_BLEUE, LOW);
    } else if (manualFanControl && currentFanLevel > 0) {
      digitalWrite(LED_BLEUE, HIGH); // Allumé en continu en mode manuel
      digitalWrite(LED_ROUGE, LOW);
    } else {
      digitalWrite(LED_ROUGE, LOW);
      digitalWrite(LED_BLEUE, LOW);
    }
    return;
  }
  
  // Mode automatique - clignotement selon le niveau
  unsigned long currentTime = millis();
  int period;
  
  if (currentHeaterLevel > 0) {
    switch(currentHeaterLevel) {
      case 1: period = 2000; break;
      case 2: period = 1500; break;
      case 3: period = 1000; break;
      case 4: period = 500; break;
      case 5: period = 250; break;
      default: period = 2000;
    }
    
    if (currentTime - lastLEDUpdate >= period) {
      ledState = !ledState;
      digitalWrite(LED_ROUGE, ledState ? HIGH : LOW);
      lastLEDUpdate = currentTime;
    }
    digitalWrite(LED_BLEUE, LOW);
    
  } else if (currentFanLevel > 0) {
    switch(currentFanLevel) {
      case 1: period = 2000; break;
      case 2: period = 1500; break;
      case 3: period = 1000; break;
      case 4: period = 500; break;
      case 5: period = 250; break;
      default: period = 2000;
    }
    
    if (currentTime - lastLEDUpdate >= period) {
      ledState = !ledState;
      digitalWrite(LED_BLEUE, ledState ? HIGH : LOW);
      lastLEDUpdate = currentTime;
    }
    digitalWrite(LED_ROUGE, LOW);
    
  } else {
    digitalWrite(LED_ROUGE, LOW);
    digitalWrite(LED_BLEUE, LOW);
    ledState = false;
  }
}

// Réinitialiser l'état des LEDs quand on change de mode
void resetLEDState() {
  ledState = false;
  lastLEDUpdate = millis();
  digitalWrite(LED_ROUGE, LOW);
  digitalWrite(LED_BLEUE, LOW);
}

// Gestion des commandes Adafruit IO
void handleAdafruitCommands() {
  Adafruit_MQTT_Subscribe *subscription;
  
  while ((subscription = mqtt.readSubscription(100))) {
    // Commande mode manuel/automatique
    if (subscription == &manualModeControl) {
      Serial.print("Commande mode: ");
      Serial.println((char *)manualModeControl.lastread);
      
      char *value = (char *)manualModeControl.lastread;
      String message = String(value);
      message.trim();
      
      bool previousMode = manualMode;
      
      if (message == "ON") {
        manualMode = true;
        Serial.println("MODE MANUEL ACTIVE");
        resetLEDState();
        needsAdafruitUpdate = true; 
      } else if (message == "OFF") {
        manualMode = false;
        manualHeaterControl = false;
        manualFanControl = false;
        Serial.println("MODE AUTOMATIQUE ACTIVE");
        resetLEDState();
        needsAdafruitUpdate = true; 
      }
    }
    
    // Commande ON/OFF chauffage (seulement en mode manuel)
    if (subscription == &chaufageControl && manualMode) {
      Serial.print("Commande chauffage: ");
      Serial.println((char *)chaufageControl.lastread);
      
      char *value = (char *)chaufageControl.lastread;
      String message = String(value);
      message.trim();
      
      if (message == "ON") {
        manualHeaterControl = true;
        manualFanControl = false;
        if (currentHeaterLevel == 0) currentHeaterLevel = 1;
        currentFanLevel = 0;
        Serial.print("Chauffage MANUEL: ON - Niveau ");
        Serial.println(currentHeaterLevel);
        resetLEDState();
        needsAdafruitUpdate = true;
      } else if (message == "OFF") {
        manualHeaterControl = false;
        currentHeaterLevel = 0;
        Serial.println("Chauffage MANUEL: OFF");
        resetLEDState();
        needsAdafruitUpdate = true;
      }
    }
    
    // Commande ON/OFF ventilateur (seulement en mode manuel)
    if (subscription == &ventilataireControl && manualMode) {
      Serial.print("Commande ventilateur: ");
      Serial.println((char *)ventilataireControl.lastread);
      
      char *value = (char *)ventilataireControl.lastread;
      String message = String(value);
      message.trim();
      
      if (message == "ON") {
        manualFanControl = true;
        manualHeaterControl = false;
        if (currentFanLevel == 0) currentFanLevel = 1;
        currentHeaterLevel = 0;
        Serial.print("Ventilateur MANUEL: ON - Niveau ");
        Serial.println(currentFanLevel);
        resetLEDState();
        needsAdafruitUpdate = true;
      } else if (message == "OFF") {
        manualFanControl = false;
        currentFanLevel = 0;
        Serial.println("Ventilateur MANUEL: OFF");
        resetLEDState();
        needsAdafruitUpdate = true;
      }
    }
    
    // Réception du niveau chauffage (en mode manuel)
    if (subscription == &heaterLevelControl && manualMode && manualHeaterControl) {
      Serial.print("Niveau chauffage recu: ");
      Serial.println((char *)heaterLevelControl.lastread);
      
      char *value = (char *)heaterLevelControl.lastread;
      String message = String(value);
      message.trim();
      
      int newLevel = message.toInt();
      if (newLevel >= 0 && newLevel <= 5) {
        currentHeaterLevel = newLevel;
        Serial.print("Niveau chauffage defini a: ");
        Serial.println(currentHeaterLevel);
        resetLEDState();
        needsAdafruitUpdate = true;
      }
    }
    
    // Réception du niveau ventilateur (en mode manuel)
    if (subscription == &fanLevelControl && manualMode && manualFanControl) {
      Serial.print("Niveau ventilateur recu: ");
      Serial.println((char *)fanLevelControl.lastread);
      
      char *value = (char *)fanLevelControl.lastread;
      String message = String(value);
      message.trim();
      
      int newLevel = message.toInt();
      if (newLevel >= 0 && newLevel <= 5) {
        currentFanLevel = newLevel;
        Serial.print("Niveau ventilateur defini a: ");
        Serial.println(currentFanLevel);
        resetLEDState();
        needsAdafruitUpdate = true;
      }
    }
  }
}

// Fonction pour publier TOUS les états vers Adafruit IO
void publishAllStatesToAdafruit(float temperature) {
  if (!wifiConnected || !mqtt.connected()) {
    return;
  }

  unsigned long currentTime = millis();
  if (currentTime - lastAdafruitPublish >= ADAFRUIT_PUBLISH_INTERVAL || needsAdafruitUpdate) {
    
    Serial.println("----------------------------------------");
    Serial.println("MISE A JOUR ETATS ADAFRUIT IO:");
    
    // Publier la température
    if (temperatureFeed.publish(temperature)) {
      Serial.print("  Temperature: ");
      Serial.print(temperature, 1);
      Serial.println(" C [OK]");
    } else {
      Serial.println("  Temperature: ECHEC");
    }
    
    // Publier les niveaux
    if (heaterLevelFeed.publish(currentHeaterLevel)) {
      Serial.print("  Niveau chauffage: ");
      Serial.println(currentHeaterLevel);
    } else {
      Serial.println("  Niveau chauffage: ECHEC");
    }
    
    if (fanLevelFeed.publish(currentFanLevel)) {
      Serial.print("  Niveau ventilateur: ");
      Serial.println(currentFanLevel);
    } else {
      Serial.println("  Niveau ventilateur: ECHEC");
    }
    
    // Publier les états ON/OFF
    String heaterState = (currentHeaterLevel > 0) ? "ON" : "OFF";
    String fanState = (currentFanLevel > 0) ? "ON" : "OFF";
    
    if (chaufageFeed.publish(heaterState.c_str())) {
      Serial.print("  Etat chauffage: ");
      Serial.println(heaterState);
    } else {
      Serial.println("  Etat chauffage: ECHEC");
    }
    
    if (ventilataireFeed.publish(fanState.c_str())) {
      Serial.print("  Etat ventilateur: ");
      Serial.println(fanState);
    } else {
      Serial.println("  Etat ventilateur: ECHEC");
    }
    
    Serial.println("----------------------------------------");
    
    lastAdafruitPublish = currentTime;
    needsAdafruitUpdate = false;
  }
}

void loop() {
  // Gérer la connexion MQTT
  if (wifiConnected) {
    MQTT_connect();
    handleAdafruitCommands();
    
    
    if (!locationPublished) {
      publishLocationInfo();
    }
    
    if (!imagePublished) {
      publishImageInfo();
    }
    
    
    if (millis() - lastLocationUpdate >= LOCATION_UPDATE_INTERVAL) {
      publishLocationInfo();
      lastLocationUpdate = millis();
    }
  }
  
  // Mettre à jour les LEDs en continu
  updateLEDs();
  
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("[ERREUR] Lecture capteur DHT22 impossible");
    delay(5000);
    return;
  }

  // ========== OBTENIR DATE ET HEURE ==========
  time_t now = time(nullptr);
  struct tm* timeinfo = localtime(&now);

  int year = timeinfo->tm_year + 1900;
  int month = timeinfo->tm_mon + 1;
  int day = timeinfo->tm_mday;
  int hour = timeinfo->tm_hour;
  int minute = timeinfo->tm_min;
  int second = timeinfo->tm_sec;

  String hourMinute = "";
  if (hour < 10) hourMinute += "0";
  hourMinute += String(hour);
  hourMinute += ":";
  if (minute < 10) hourMinute += "0";
  hourMinute += String(minute);

  // ========== AFFICHAGE DONNEES CAPTEUR ==========
  Serial.println("----------------------------------------");
  Serial.print("Date/Heure : ");
  if (day < 10) Serial.print("0");
  Serial.print(day);
  Serial.print("/");
  if (month < 10) Serial.print("0");
  Serial.print(month);
  Serial.print("/");
  Serial.print(year);
  Serial.print(" ");
  Serial.print(hourMinute);
  Serial.print(":");
  if (second < 10) Serial.print("0");
  Serial.println(second);

  Serial.print("Temperature: ");
  Serial.print(t, 1);
  Serial.println(" C");

  Serial.print("Humidite   : ");
  Serial.print(h, 1);
  Serial.println(" %");

  // ========== CONFIGURATION SEUILS ==========
  float seuil_chaud = 25.0;
  float seuil_froid = 22.0;

  int heater_level = 0;
  int fan_level = 0;

  // ========== ANALYSE TEMPERATURE ET CONTROLE ==========
  Serial.println("----------------------------------------");

  if (!manualMode) {
    // Mode automatique
    if (t >= seuil_chaud) {
      float diff = t - seuil_chaud;
      fan_level = niveauVentilateur(diff);
      heater_level = 0;

      Serial.println("ETAT SYSTEME: CLIMATISATION ACTIVE (AUTO)");
      Serial.print("  Niveau Fan : ");
      Serial.print(fan_level);
      Serial.print("/5  |  Ecart: +");
      Serial.print(diff, 1);
      Serial.println(" C");

    }
    else if (t <= seuil_froid) {
      float diff = seuil_froid - t;
      heater_level = niveauChauffage(diff);
      fan_level = 0;

      Serial.println("ETAT SYSTEME: CHAUFFAGE ACTIF (AUTO)");
      Serial.print("  Niveau Heat: ");
      Serial.print(heater_level);
      Serial.print("/5  |  Ecart: -");
      Serial.print(diff, 1);
      Serial.println(" C");

    }
    else {
      heater_level = 0;
      fan_level = 0;
      Serial.println("ETAT SYSTEME: TEMPERATURE OPTIMALE (AUTO)");
    }
    
    // Mettre à jour les niveaux courants pour le contrôle des LEDs
    currentHeaterLevel = heater_level;
    currentFanLevel = fan_level;
    needsAdafruitUpdate = true; 
    
  } else {
    // Mode manuel - respecte les niveaux choisis par l'utilisateur
    Serial.println("ETAT SYSTEME: MODE MANUEL ACTIF");
    
    if (manualHeaterControl) {
      heater_level = currentHeaterLevel;
      fan_level = 0;
      Serial.print("  Chauffage: ON - Niveau ");
      Serial.print(heater_level);
      Serial.println("/5 (Manuel)");
    } else if (manualFanControl) {
      heater_level = 0;
      fan_level = currentFanLevel;
      Serial.print("  Ventilateur: ON - Niveau ");
      Serial.print(fan_level);
      Serial.println("/5 (Manuel)");
    } else {
      heater_level = 0;
      fan_level = 0;
      Serial.println("  Aucun appareil actif (Manuel)");
    }
  }

  // ========== PUBLICATION VERS ADAFRUIT IO ==========
  publishAllStatesToAdafruit(t);

  // ========== TRANSMISSION DONNEES A NODE-RED/AZURE ==========
  Serial.println("----------------------------------------");
  if (wifiConnected && WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;

    http.begin(client, serverUrl);
    http.addHeader("Content-Type", "application/json");

    // Format JSON 
    String jsonData = "{";
    jsonData += "\"year\":" + String(year) + ",";
    jsonData += "\"month\":" + String(month) + ",";
    jsonData += "\"day\":" + String(day) + ",";
    jsonData += "\"hour\":\"" + hourMinute + "\",";
    jsonData += "\"indoor_temp\":" + String(t, 2) + ",";
    jsonData += "\"heater_level\":" + String(currentHeaterLevel) + ",";
    jsonData += "\"fan_level\":" + String(currentFanLevel);
    jsonData += "}";

    Serial.println("TRANSMISSION NODE-RED:");
    Serial.print("  Destination: ");
    Serial.println(serverUrl);
    Serial.print("  Payload    : ");
    Serial.println(jsonData);

    int httpResponseCode = http.POST(jsonData);

    if (httpResponseCode > 0) {
      String response = http.getString();
      Serial.print("  Statut HTTP: ");
      Serial.print(httpResponseCode);
      Serial.println(" [OK]");
    } else {
      Serial.print("  Statut HTTP: ");
      Serial.print(httpResponseCode);
      Serial.println(" [ERREUR]");
    }

    http.end();
  } else if (!wifiConnected) {
    Serial.println("TRANSMISSION DONNEES: DESACTIVEE");
    Serial.println("  Raison: WiFi non connecte");
  }

  Serial.println("========================================");
  Serial.print("Prochaine capture dans 60 secondes...");
  Serial.println();

  // Attendre 60 secondes en maintenant le contrôle des LEDs et MQTT
  unsigned long startWait = millis();
  while (millis() - startWait < 60000) {
    if (wifiConnected) {
      MQTT_connect();
      handleAdafruitCommands();
    }
    updateLEDs();
    delay(100);
  }
}