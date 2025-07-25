Interchainedd Beta Testing Guide

This guide is designed for testers to evaluate the Interchainedd Mobile wallet before public release.

⸻

1. Installation
	•	Obtain the latest signed APK from the official Interchainedd repository or direct link.
	•	Verify Integrity: Check the SHA256 checksum matches the official value provided.
	•	Install on an Android device (enable Install from Unknown Sources if necessary).

⸻

2. Wallet Testing Tasks

A. Create & Backup Wallet
	•	Create a new ITC wallet.
	•	Write down the 12/24-word seed phrase.
	•	Verify you can restore the wallet using the backup phrase.

B. Address Generation
	•	Confirm addresses use the itc1... bech32 prefix.
	•	Generate multiple receive addresses and verify they are unique.

C. Send & Receive ITC
	•	Send a small ITC transaction to your wallet.
	•	Send ITC from your wallet to another address.
	•	Verify confirmations and transaction details on the Interchained explorer.

D. Fee Validation
	•	Confirm dynamic fee calculation works correctly.
	•	Test low/medium/high fee settings and check confirmation times.

E. Recovery Test
	•	Uninstall the app and reinstall.
	•	Restore wallet from seed phrase.
	•	Confirm balance and transaction history matches.

⸻

3. UI/UX Checks
	•	Verify branding: Interchained logo, ticker ITC, and correct colors.
	•	Check dark/light mode behavior.
	•	Validate that all references to BTC/Bitcoin are removed.

⸻

4. Connectivity & Explorer
	•	Confirm ElectrumX server connects via SSL.
	•	Verify transaction history and balances are accurate.
	•	Check explorer links open correctly from the wallet.

⸻

5. Bug Reporting
	•	Use the official bug reporting form or GitHub Issues.
	•	Include:
	•	Steps to reproduce the issue.
	•	Device model & Android version.
	•	Screenshots or logs if possible.

⸻

Goal: Testers should confirm wallet reliability, address correctness, backup/restore functionality, and transaction success before public launch.
