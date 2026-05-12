name: Monthly MA10 Scanner

on:
  schedule:
    # รันจันทร์ - ศุกร์ เวลา 15:00 น. ไทย (08:00 UTC)
    - cron: '0 8 * * 1-5'
  workflow_dispatch: # ปุ่มกดรันเองในหน้า Actions

jobs:
  scanner_job:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install Libs
        run: pip install yfinance pandas requests

      - name: Execute Scan
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
        run: python monthly_scanner.py
