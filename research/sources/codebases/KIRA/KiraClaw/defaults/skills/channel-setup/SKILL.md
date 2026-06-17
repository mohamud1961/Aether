---
name: channel-setup
description: Use when the user asks how to connect or configure Slack, Telegram, or Discord in KiraClaw, including which token or settings field to fill in, what platform-side setup is required, and when an engine restart is needed.
---

# Channel Setup Guide

Use this skill when the user wants to connect KiraClaw to Slack, Telegram, or Discord from the `Channels` screen.

## General Rules

- Open `Settings > Channels`.
- Fill in the fields for the platform you want to enable.
- Save the settings.
- Restart the engine after enabling or changing channel credentials.
- `Allowed Names` should include the human names or handles that are allowed to talk to the bot on that platform.

## Slack

Fill in:

- `Slack Enabled`
- `Slack Bot Token`
- `Slack App Token`
- `Slack Signing Secret`
- `Slack Team ID`
- `Slack Allowed Names`

Required Slack-side setup:

- Install the Slack app into the target workspace.
- Ensure the bot is invited to the channels you want it to read or post in.
- If testing in a channel, mention the bot or talk in a DM depending on the current channel rules.

## Telegram

Fill in:

- `Telegram Enabled`
- `Telegram Bot Token`
- `Telegram Allowed Names`

Required Telegram-side setup:

- Create a bot with `@BotFather` and copy the bot token.
- Add the bot to the target DM, group, or channel.
- For groups, mention the bot when needed.
- If group behavior is limited, check the bot privacy settings in `BotFather`.

## Discord

Fill in:

- `Discord Enabled`
- `Discord Bot Token`
- `Discord Allowed Names`

Required Discord-side setup:

- Create a Discord application and bot in the Discord Developer Portal.
- Copy the bot token into `Discord Bot Token`.
- Enable the `Message Content Intent` for the bot.
- Invite the bot to the server with the required read/send permissions.

## Practical Advice

- If the user is unsure what to enter, explain the fields one by one.
- If a platform is not responding, first check the token, then whether the bot was invited, then whether the engine was restarted.
- If the user asks for live diagnosis, inspect runtime status and recent logs after confirming the channel was saved and restarted.
