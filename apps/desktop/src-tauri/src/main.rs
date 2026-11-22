// Empêche l'ouverture d'une console supplémentaire sous Windows en version distribuée.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    statpfe_lib::run()
}
