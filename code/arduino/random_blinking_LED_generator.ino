/*

Simple Arduino 1-Channel random TTL Generator

*/

int TTL_PIN         = 12;  // pull high to output

int pulse_duration  = 225; // at 40fps 225ms should be 9 picamera frames

int min_pulse_space = 250; // at 40fps 250ms should be 10 picamera frames

int max_pulse_space = 525; // at 40fps 525ms should be 21 picamera frames

int pulse_space;

void setup() {

// define pin as digital output

pinMode(TTL_PIN, OUTPUT);

// if analog input pin 0 is unconnected, random analog

// noise will cause the call to randomSeed() to generate

// different seed numbers each time the sketch runs.

// randomSeed() will then shuffle the random function.

randomSeed(analogRead(0));

}

void loop() {

// a random number between min and max-1

pulse_space = random(min_pulse_space, max_pulse_space+1);

//pulse_space = random(1,3);

digitalWrite(TTL_PIN, LOW);

delay(pulse_space);

digitalWrite(TTL_PIN, HIGH);

delay(pulse_duration);

}
