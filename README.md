name: Desi Life Daily Automation

on:
  schedule:
    - cron: '0 4 * * *'
    - cron: '0 10 * * *'
  workflow_dispatch:
    inputs:
      mode:
        description: 'Video type'
        required: true
        default: 'long'
        type: choice
        options:
          - long
          - short

jobs:
  upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run LONG video
        if: github.event.schedule == '0 4 * * *' || (github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'long')
        env:
          GEMINI_KEY: ${{ secrets.GEMINI_KEY }}
          PEXELS_KEY: ${{ secrets.PEXELS_KEY }}
          YOUTUBE_CLIENT_ID: ${{ secrets.YOUTUBE_CLIENT_ID }}
          YOUTUBE_CLIENT_SECRET: ${{ secrets.YOUTUBE_CLIENT_SECRET }}
          YOUTUBE_REFRESH_TOKEN: ${{ secrets.YOUTUBE_REFRESH_TOKEN }}
          MODE: long
        run: python final_cloud_bot.py

      - name: Run SHORT video
        if: github.event.schedule == '0 10 * * *' || (github.event_name == 'workflow_dispatch' && github.event.inputs.mode == 'short')
        env:
          GEMINI_KEY: ${{ secrets.GEMINI_KEY }}
          PEXELS_KEY: ${{ secrets.PEXELS_KEY }}
          YOUTUBE_CLIENT_ID: ${{ secrets.YOUTUBE_CLIENT_ID }}
          YOUTUBE_CLIENT_SECRET: ${{ secrets.YOUTUBE_CLIENT_SECRET }}
          YOUTUBE_REFRESH_TOKEN: ${{ secrets.YOUTUBE_REFRESH_TOKEN }}
          MODE: short
        run: python final_cloud_bot.py
