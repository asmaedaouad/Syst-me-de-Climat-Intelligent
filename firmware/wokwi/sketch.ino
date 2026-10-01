#include <ESP32Servo.h>
#include <DHT.h>
#include <LiquidCrystal_I2C.h>
#include <ThingSpeak.h>
#include <WiFi.h>
#include <HTTPClient.h>

// ==== Configuration WiFi et ThingSpeak ====
const char* ssid = "Wokwi-GUEST";
const char* password = "";
const char* thingSpeakApiKey = "YOUR_THINGSPEAK_WRITE_KEY";
unsigned long thingSpeakChannelID = 0 /* YOUR_CHANNEL_ID */;

// ==== Configuration CallMeBot WhatsApp ====
String phoneNumber = "+212XXXXXXXXX"; 
String apiKey = "YOUR_CALLMEBOT_KEY"; 

// ==== Configuration des broches ====
#define DHT22_PIN 23
#define LED_ROUGE 26
#define LED_BLEUE 25
#define FAN_PIN 32

// ==== Seuils de température ====
#define TEMP_FROID_EXTREME 15.0
#define TEMP_FROID 20.0
#define TEMP_CONFORT_MIN 20.0
#define TEMP_CONFORT_MAX 25.0
#define TEMP_CHAUD 25.0
#define TEMP_CHAUD_EXTREME 40.0

// ==== Initialisation ====
DHT dht22(DHT22_PIN, DHT22);
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo fanServo;
WiFiClient client;

// ==== Variables globales ====
unsigned long dernierMouvement = 0;
unsigned long derniereLecture = 0;
unsigned long dernierClignotement = 0;
unsigned long dernierEnvoiThingSpeak = 0;
unsigned long dernierEnvoiWhatsApp = 0; // Nouveau
const unsigned long INTERVALLE_LECTURE = 2000;
const unsigned long INTERVALLE_THINGSPEAK = 20000; // Envoi toutes les 20 secondes
const unsigned long INTERVALLE_WHATSAPP = 60000; // Envoi toutes les 60 secondes
int angleVentilateur = 90;
int vitesseVentilateur = 0;
bool directionCroissante = true;
float derniereTemp = 22.0;
float derniereHumi = 50.0;
bool etatClignotement = false;

// ==== États du système ====
enum EtatSysteme {
  CHAUFFAGE_MAX,
  CHAUFFAGE_DOUX,
  CONFORT,
  VENTILATION_FAIBLE,
  VENTILATION_MOYENNE,
  VENTILATION_FORTE,
  ERREUR
};

EtatSysteme etatActuel = CONFORT;

// ==== Fonction pour encoder l'URL ====
String urlEncode(String str) {
  String encodedString = "";
  char c;
  char code0;
  char code1;
  
  for (int i = 0; i < str.length(); i++) {
    c = str.charAt(i);
    if (c == ' ') {
      encodedString += '+';
    } else if (isalnum(c)) {
      encodedString += c;
    } else {
      code1 = (c & 0xf) + '0';
      if ((c & 0xf) > 9) {
        code1 = (c & 0xf) - 10 + 'A';
      }
      c = (c >> 4) & 0xf;
      code0 = c + '0';
      if (c > 9) {
        code0 = c - 10 + 'A';
      }
      encodedString += '%';
      encodedString += code0;
      encodedString += code1;
    }
  }
  return encodedString;
}

// ==== Fonction pour envoyer message WhatsApp ====
void envoyerWhatsApp(String message) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi non connecté - impossible d'envoyer WhatsApp");
    return;
  }
  
  String url = "https://api.callmebot.com/whatsapp.php?phone=" + phoneNumber + 
               "&text=" + urlEncode(message) + 
               "&apikey=" + apiKey;
  
  HTTPClient http;
  http.begin(url);
  
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");
  
  int httpResponseCode = http.GET();
  
  if (httpResponseCode == 200) {
    Serial.println("Message WhatsApp envoyé avec succès!");
  } else {
    Serial.print("Erreur envoi WhatsApp. Code: ");
    Serial.println(httpResponseCode);
  }
  
  http.end();
}

// ==== Fonction pour créer le message de statut ====
String creerMessageStatut() {
  String message = "Temperature : " + String(derniereTemp, 1) + " C\n";
  message += "Humidite : " + String(derniereHumi, 0) + "%\n";
  
  // État du chauffage
  if (etatActuel == CHAUFFAGE_MAX || etatActuel == CHAUFFAGE_DOUX) {
    message += "Chauffage : ON\n";
    message += "Ventilateur : OFF";
  } else if (etatActuel == CONFORT) {
    message += "Chauffage : OFF\n";
    message += "Ventilateur : OFF";
  } else {
    message += "Chauffage : OFF\n";
    message += "Ventilateur : " + String(vitesseVentilateur) + "%";
  }
  
  return message;
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Système de Gestion Intelligente de Climat ===");
  
  // Initialisation des composants
  dht22.begin();
  lcd.init();
  lcd.backlight();
  
  // Configuration des LEDs en mode digital
  pinMode(LED_ROUGE, OUTPUT);
  pinMode(LED_BLEUE, OUTPUT);
  digitalWrite(LED_ROUGE, LOW);
  digitalWrite(LED_BLEUE, LOW);
  
  // Configuration du servo - IMPORTANT: allouer les timers
  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  
  fanServo.setPeriodHertz(50);
  fanServo.attach(FAN_PIN, 500, 2400);
  
  // Connexion WiFi
  connecterWiFi();
  
  // Initialisation ThingSpeak
  ThingSpeak.begin(client);
  
  // Test du servo au démarrage
  Serial.println("Test du servo...");
  fanServo.write(0);
  delay(500);
  fanServo.write(90);
  delay(500);
  fanServo.write(180);
  delay(500);
  fanServo.write(90);
  Serial.println("Servo OK!");
  
  // Message de démarrage
  lcd.setCursor(0, 0);
  lcd.print("Systeme Climat");
  lcd.setCursor(0, 1);
  lcd.print("Initialisation..");
  
  // Animation de démarrage simple
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_ROUGE, HIGH);
    delay(200);
    digitalWrite(LED_ROUGE, LOW);
    digitalWrite(LED_BLEUE, HIGH);
    delay(200);
    digitalWrite(LED_BLEUE, LOW);
  }
  
  lcd.clear();
  Serial.println("Système initialisé avec succès!");
  
  // Envoi du message de démarrage sur WhatsApp
  envoyerWhatsApp("Systeme de climat demarre!\n" + creerMessageStatut());
}

void loop() {
  unsigned long maintenant = millis();
  
  // Lecture des capteurs à intervalle régulier
  if (maintenant - derniereLecture >= INTERVALLE_LECTURE) {
    derniereLecture = maintenant;
    
    float tempC = dht22.readTemperature();
    float humi = dht22.readHumidity();

    if (isnan(tempC) || isnan(humi)) {
      gererErreur();
    } else {
      derniereTemp = tempC;
      derniereHumi = humi;
      
      afficherDonnees(tempC, humi);
      controlerSysteme(tempC);
      afficherMoniteurSerie(tempC, humi);
    }
  }
  
  // Envoi des données à ThingSpeak à intervalle régulier
  if (maintenant - dernierEnvoiThingSpeak >= INTERVALLE_THINGSPEAK) {
    dernierEnvoiThingSpeak = maintenant;
    envoyerDonneesThingSpeak();
  }
  
  // Envoi des données à WhatsApp à intervalle régulier
  if (maintenant - dernierEnvoiWhatsApp >= INTERVALLE_WHATSAPP) {
    dernierEnvoiWhatsApp = maintenant;
    envoyerWhatsApp(creerMessageStatut());
  }
  
  // Gestion continue de la rotation du ventilateur
  if (vitesseVentilateur > 0) {
    gererRotationVentilateur();
  }
  
  // Gestion continue des LEDs selon la température
  gererLedsSelonTemperature(derniereTemp);
  
  delay(10);
}

void connecterWiFi() {
  Serial.print("Connexion au WiFi");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connexion WiFi");
  
  WiFi.begin(ssid, password);
  
  int tentatives = 0;
  while (WiFi.status() != WL_CONNECTED && tentatives < 20) {
    delay(500);
    Serial.print(".");
    lcd.setCursor(tentatives % 16, 1);
    lcd.print(".");
    tentatives++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnecté au WiFi!");
    Serial.print("Adresse IP: ");
    Serial.println(WiFi.localIP());
    
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("WiFi OK");
    lcd.setCursor(0, 1);
    lcd.print("IP: ");
    lcd.print(WiFi.localIP());
    delay(2000);
    lcd.clear();
  } else {
    Serial.println("\nErreur connexion WiFi!");
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Erreur WiFi");
    lcd.setCursor(0, 1);
    lcd.print("Mode local");
    delay(2000);
    lcd.clear();
  }
}

void envoyerDonneesThingSpeak() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi non connecté - tentative de reconnexion");
    connecterWiFi();
    return;
  }
  
  Serial.println("Envoi des données à ThingSpeak...");
  
  // Field 1: Température
  ThingSpeak.setField(1, derniereTemp);
  
  // Field 2: Humidité
  ThingSpeak.setField(2, derniereHumi);
  
  // Field 3: Vitesse du ventilateur
  ThingSpeak.setField(3, vitesseVentilateur);
  
  // Field 4: État LED Rouge (0 ou 1)
  int etatLedRouge = digitalRead(LED_ROUGE);
  ThingSpeak.setField(4, etatLedRouge);
  
  // Field 5: État LED Bleue (0 ou 1)
  int etatLedBleue = digitalRead(LED_BLEUE);
  ThingSpeak.setField(5, etatLedBleue);
  
  // Envoi des données
  int codeReponse = ThingSpeak.writeFields(thingSpeakChannelID, thingSpeakApiKey);
  
  if (codeReponse == 200) {
    Serial.println("Données envoyées avec succès à ThingSpeak!");
    
    // Affichage temporaire sur LCD
    lcd.setCursor(13, 0);
    lcd.print("TS");
    lcd.setCursor(13, 1);
    lcd.print("OK");
    
  } else {
    Serial.print("Erreur envoi ThingSpeak. Code: ");
    Serial.println(codeReponse);
    
    // Affichage temporaire sur LCD
    lcd.setCursor(13, 0);
    lcd.print("TS");
    lcd.setCursor(13, 1);
    lcd.print("ER");
  }
  
  // Effacer l'affichage ThingSpeak après 2 secondes
  delay(2000);
  afficherDonnees(derniereTemp, derniereHumi);
  afficherEtat();
}

void afficherDonnees(float tempC, float humi) {
  lcd.setCursor(0, 0);
  lcd.print("T:");
  
  if (tempC < 10) lcd.print(" ");
  lcd.print(tempC, 1);
  lcd.print("C H:");
  
  if (humi < 10) lcd.print(" ");
  if (humi < 100) lcd.print(" ");
  lcd.print(humi, 0);
  lcd.print("%");
}

void controlerSysteme(float tempC) {
  EtatSysteme nouvelEtat;
  
  // Détermination de l'état du système
  if (tempC < TEMP_FROID_EXTREME) {
    nouvelEtat = CHAUFFAGE_MAX;
    vitesseVentilateur = 0;
    fanServo.write(0);
    Serial.println("Servo -> 0 degres (CHAUFFAGE MAX)");
    
  } else if (tempC < TEMP_FROID) {
    nouvelEtat = CHAUFFAGE_DOUX;
    vitesseVentilateur = 0;
    fanServo.write(45);
    Serial.println("Servo -> 45 degres (CHAUFFAGE DOUX)");
    
  } else if (tempC >= TEMP_CONFORT_MIN && tempC <= TEMP_CONFORT_MAX) {
    nouvelEtat = CONFORT;
    vitesseVentilateur = 0;
    fanServo.write(90);
    Serial.println("Servo -> 90 degres (CONFORT)");
    
  } else if (tempC > TEMP_CHAUD) {
    // Calcul de la vitesse proportionnelle à la température
    vitesseVentilateur = map(
      constrain(tempC * 10, TEMP_CHAUD * 10, TEMP_CHAUD_EXTREME * 10),
      TEMP_CHAUD * 10,
      TEMP_CHAUD_EXTREME * 10,
      20,
      100
    );
    
    Serial.print("Servo -> ROTATION (vitesse: ");
    Serial.print(vitesseVentilateur);
    Serial.println("%)");
    
    // Détermination du niveau de ventilation
    if (vitesseVentilateur < 40) {
      nouvelEtat = VENTILATION_FAIBLE;
    } else if (vitesseVentilateur < 70) {
      nouvelEtat = VENTILATION_MOYENNE;
    } else {
      nouvelEtat = VENTILATION_FORTE;
    }
  }
  
  // Mise à jour de l'affichage si l'état a changé
  if (nouvelEtat != etatActuel) {
    etatActuel = nouvelEtat;
    afficherEtat();
  }
}

void gererLedsSelonTemperature(float tempC) {
  unsigned long maintenant = millis();
  
  // ===== ZONE FROIDE - LED BLEUE UNIQUEMENT =====
  if (tempC < TEMP_FROID_EXTREME) {
    // < 15°C : LED bleue CLIGNOTEMENT RAPIDE
    if (maintenant - dernierClignotement > 200) {
      dernierClignotement = maintenant;
      etatClignotement = !etatClignotement;
      digitalWrite(LED_BLEUE, etatClignotement ? HIGH : LOW);
      digitalWrite(LED_ROUGE, LOW);
    }
    
  } else if (tempC < TEMP_FROID) {
    // 15-20°C : LED bleue CLIGNOTEMENT LENT
    if (maintenant - dernierClignotement > 500) {
      dernierClignotement = maintenant;
      etatClignotement = !etatClignotement;
      digitalWrite(LED_BLEUE, etatClignotement ? HIGH : LOW);
      digitalWrite(LED_ROUGE, LOW);
    }
    
  // ===== ZONE CONFORT - TOUTES ÉTEINTES =====
  } else if (tempC >= TEMP_CONFORT_MIN && tempC <= TEMP_CONFORT_MAX) {
    // 20-25°C : Toutes les LEDs éteintes
    digitalWrite(LED_ROUGE, LOW);
    digitalWrite(LED_BLEUE, LOW);
    
  // ===== ZONE CHAUDE - LED ROUGE UNIQUEMENT =====
  } else if (tempC > TEMP_CHAUD && tempC <= 28.0) {
    // 25-28°C : LED rouge ALLUMÉE
    digitalWrite(LED_ROUGE, HIGH);
    digitalWrite(LED_BLEUE, LOW);
    
  } else if (tempC > 28.0 && tempC <= 32.0) {
    // 28-32°C : LED rouge CLIGNOTEMENT MOYEN
    if (maintenant - dernierClignotement > 400) {
      dernierClignotement = maintenant;
      etatClignotement = !etatClignotement;
      digitalWrite(LED_ROUGE, etatClignotement ? HIGH : LOW);
      digitalWrite(LED_BLEUE, LOW);
    }
    
  } else if (tempC > 32.0) {
    // > 32°C : LED rouge CLIGNOTEMENT RAPIDE
    if (maintenant - dernierClignotement > 150) {
      dernierClignotement = maintenant;
      etatClignotement = !etatClignotement;
      digitalWrite(LED_ROUGE, etatClignotement ? HIGH : LOW);
      digitalWrite(LED_BLEUE, LOW);
    }
  }
}

void afficherEtat() {
  lcd.setCursor(0, 1);
  
  switch (etatActuel) {
    case CHAUFFAGE_MAX:
      lcd.print("CHAUF MAX      ");
      break;
      
    case CHAUFFAGE_DOUX:
      lcd.print("CHAUF DOUX     ");
      break;
      
    case CONFORT:
      lcd.print("CONFORT        ");
      break;
      
    case VENTILATION_FAIBLE:
      lcd.print("VENTIL ");
      lcd.print(vitesseVentilateur);
      lcd.print("%    ");
      break;
      
    case VENTILATION_MOYENNE:
      lcd.print("VENTIL ");
      lcd.print(vitesseVentilateur);
      lcd.print("%   ");
      break;
      
    case VENTILATION_FORTE:
      lcd.print("VENTIL ");
      lcd.print(vitesseVentilateur);
      lcd.print("% !!!");
      break;
      
    case ERREUR:
      lcd.print("ERREUR CAPTEUR!");
      break;
  }
}

void gererRotationVentilateur() {
  unsigned long maintenant = millis();
  
  // Calcul du délai basé sur la vitesse
  int delai = map(vitesseVentilateur, 20, 100, 50, 10);
  
  if (maintenant - dernierMouvement > delai) {
    dernierMouvement = maintenant;
    
    // Rotation en va-et-vient (0° à 180°)
    if (directionCroissante) {
      angleVentilateur += 10;
      if (angleVentilateur >= 180) {
        angleVentilateur = 180;
        directionCroissante = false;
      }
    } else {
      angleVentilateur -= 10;
      if (angleVentilateur <= 0) {
        angleVentilateur = 0;
        directionCroissante = true;
      }
    }
    
    fanServo.write(angleVentilateur);
    
    // Debug tous les 30 degrés
    if (angleVentilateur % 30 == 0) {
      Serial.print("Servo rotation: ");
      Serial.print(angleVentilateur);
      Serial.println(" degres");
    }
  }
}

void gererErreur() {
  etatActuel = ERREUR;
  vitesseVentilateur = 0;
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("ERREUR CAPTEUR!");
  lcd.setCursor(0, 1);
  lcd.print("Verifier DHT22");
  
  fanServo.write(90);
  
  Serial.println("ERREUR: Impossible de lire le capteur DHT22!");
  
  // Clignotement alterné des LEDs pour indiquer l'erreur
  unsigned long maintenant = millis();
  if (maintenant - dernierClignotement > 300) {
    dernierClignotement = maintenant;
    etatClignotement = !etatClignotement;
    digitalWrite(LED_ROUGE, etatClignotement ? HIGH : LOW);
    digitalWrite(LED_BLEUE, etatClignotement ? LOW : HIGH);
  }
}

void afficherMoniteurSerie(float tempC, float humi) {
  Serial.println("================================");
  Serial.print("Temperature: ");
  Serial.print(tempC, 1);
  Serial.println(" C");
  
  Serial.print("Humidite: ");
  Serial.print(humi, 1);
  Serial.println(" %");
  
  Serial.print("Etat: ");
  switch (etatActuel) {
    case CHAUFFAGE_MAX:
      Serial.println("CHAUFFAGE MAXIMUM");
      Serial.println("LED Bleue: CLIGNOTEMENT RAPIDE");
      Serial.println("Servo: 0 degres");
      break;
    case CHAUFFAGE_DOUX:
      Serial.println("CHAUFFAGE DOUX");
      Serial.println("LED Bleue: CLIGNOTEMENT LENT");
      Serial.println("Servo: 45 degres");
      break;
    case CONFORT:
      Serial.println("ZONE DE CONFORT");
      Serial.println("LEDs: TOUTES ETEINTES");
      Serial.println("Servo: 90 degres");
      break;
    case VENTILATION_FAIBLE:
      Serial.print("VENTILATION FAIBLE (");
      Serial.print(vitesseVentilateur);
      Serial.println("%)");
      Serial.println("LED Rouge: ALLUMEE");
      Serial.println("Servo: ROTATION");
      break;
    case VENTILATION_MOYENNE:
      Serial.print("VENTILATION MOYENNE (");
      Serial.print(vitesseVentilateur);
      Serial.println("%)");
      Serial.println("LED Rouge: CLIGNOTEMENT MOYEN");
      Serial.println("Servo: ROTATION");
      break;
    case VENTILATION_FORTE:
      Serial.print("VENTILATION FORTE (");
      Serial.print(vitesseVentilateur);
      Serial.println("%)");
      Serial.println("LED Rouge: CLIGNOTEMENT RAPIDE");
      Serial.println("Servo: ROTATION RAPIDE");
      break;
    case ERREUR:
      Serial.println("ERREUR");
      Serial.println("LEDs: CLIGNOTEMENT ALTERNE");
      break;
  }
  
  Serial.print("Vitesse ventilateur: ");
  Serial.print(vitesseVentilateur);
  Serial.println("%");
  
  Serial.print("Angle servo actuel: ");
  Serial.print(angleVentilateur);
  Serial.println(" degres");
  
  Serial.print("LED Rouge: ");
  Serial.println(digitalRead(LED_ROUGE) ? "ON" : "OFF");
  
  Serial.print("LED Bleue: ");
  Serial.println(digitalRead(LED_BLEUE) ? "ON" : "OFF");
  
  Serial.println("================================\n");
}