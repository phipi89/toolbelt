compose_mail() {
    URL="https://outlook.office.com/mail/0/deeplink/compose"
    chromium --app="$URL" &
}