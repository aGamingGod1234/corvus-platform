fn main() {
    if let Err(error) = corvus_desktop::run() {
        eprintln!("Corvus desktop failed: {error}");
        std::process::exit(1);
    }
}
