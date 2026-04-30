terraform {
  backend "gcs" {
    bucket = "jackpot-production-tfstate"
    prefix = "terraform/state"
  }
}
