terraform {
  backend "gcs" {
    bucket = "jackpot-staging-tfstate"
    prefix = "terraform/state"
  }
}
