Interchainedd Launch Readiness Checklist

This checklist captures the final tasks to verify before public launch.

⸻

1. Branding & UX
	•	App Icons & Splash Screens: Replace all BlueWallet assets with Interchained branding.
	•	Ticker & Copy Audit: Confirm all BTC/Bitcoin references are fully replaced with ITC/Interchained.
	•	Theme Polishing: Ensure color palette, dark/light mode, and logos are consistent.

⸻

2. Wallet Testing
	•	Seed Backup & Restore: Verify creating, backing up, and restoring a wallet works flawlessly.
	•	Transaction Flow: Test send/receive ITC on mainnet and testnet.
	•	Fee Calculation: Confirm dynamic fees (or static fallback) are correct and transactions confirm promptly.
	•	Multiple Device Testing: Install APK on different Android versions (emulator + physical devices).

⸻

3. Infrastructure Validation
	•	ElectrumX SSL Endpoint: Confirm mobile wallet connects without errors.
	•	Explorer/API Sync: Verify block height, mempool, and transaction history.
	•	Monitoring: Ensure node uptime alerts (Prometheus/Grafana or basic scripts) are active.

⸻

4. Distribution
	•	Signed APK Verification: Validate the SHA256 checksum of the final signed APK.
	•	Closed Beta Testing: Provide APK to a small test group for feedback.
	•	Google Play Compliance: Privacy Policy, Data Safety, target SDK 34 (if Play Store release planned).

⸻

5. Launch Prep
	•	Status Page: Simple web page with block height, network health, and links (explorer, wallet download).
	•	Announcement Content: Draft social posts, website updates, and GitHub README.
	•	Backup Keys: Ensure keystore, signing keys, and ElectrumX certs are backed up securely.

⸻

Goal: Once all items are checked, Interchainedd Mobile is production-ready for its first public release!
