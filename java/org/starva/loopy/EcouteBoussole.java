package org.starva.loopy;

import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;

/** Garde la dernière mesure du capteur d'orientation ; Python la lit quand il veut.
 *  Android n'appelle donc jamais Python depuis son propre fil (un rappel pyjnius dans l'app faisait planter). */
public class EcouteBoussole implements SensorEventListener {
    public volatile float[] valeurs;

    @Override
    public void onSensorChanged(SensorEvent event) {
        valeurs = event.values.clone();
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int precision) {
    }
}
