# React Native Mobile App

This directory contains a simple React Native application using Expo. It includes
three pages:

- **Home** – displays the current balance and a list of recent transactions from
your API. Tapping a transaction opens the details screen. A button navigates to
the transfer page.
- **Transaction Details** – shows extra information about a specific
transaction.
- **Transfer** – lets you send a payment to a public address. The amount is
parsed in 8 decimal places and submitted to your API.

Replace the `https://example.com/api` URLs in the source with your actual API
endpoints.

## Development

```bash
npm install -g expo-cli
cd mobile/app
npm install
expo start
```

This will launch the Expo development server so you can run the app on iOS,
Android or web.
