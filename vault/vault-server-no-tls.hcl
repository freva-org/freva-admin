ui = true


listener "tcp" {
  address          = "127.0.0.1:8200"
  tls_disable      = "true"
}

api_addr="https://127.0.0.1:8200"

storage "file" {
  path = "/vault/file"
}
