Interchainedd Launch Board

This board outlines all major tasks required to get Interchainedd mobile, infrastructure, and ecosystem ready for a public launch.

⸻

P0: Launch Blockers (Must-Have)

Infrastructure & Chain
	•	ElectrumX Hardening
	•	Configure systemd with Restart=always and proper LimitNOFILE.
	•	SSL cert auto-renew (Let’s Encrypt or other).
	•	DoS protection & connection limits.
	•	Redundant Nodes
	•	Deploy a secondary ElectrumX server.
	•	Set up DNS failover (e.g., electrum.interchained.org).
	•	Monitoring
	•	Deploy Prometheus + Grafana.
	•	Alerts for chain height lag, mempool backlog, and ElectrumX errors.
	•	Explorer API
	•	Ensure /api/address, /api/tx, /api/block endpoints are stable.
	•	Add /api/fee-estimates for wallet fee calculations.

Mobile Wallet
	•	Network Library Fork
	•	Complete fork of bitcoinjs-lib -> interchainedjs-lib.
	•	Pin versions and update imports in BlueWallet.
	•	Address & Key Verification
	•	Verify itc1... addresses match wallet seed/derivation.
	•	Confirm BIP32 paths and SLIP-0044 coin type.
	•	Electrum Config
	•	Point mobile app to production ElectrumX endpoints.
	•	Enable SSL with fallback options.
	•	Crash & Error Logging
	•	Add Bugsnag or Sentry (anonymized error logs).
	•	App Signing
	•	Secure keystore backup & rotation plan.

Compliance & Distribution
	•	Play Store Checklist
	•	Target SDK 34.
	•	Data Safety & Privacy Policy.
	•	App icon & branding (Interchained logo).
	•	Side-Load Release
	•	Provide signed APK with SHA256 hash.

⸻

P1: Post-Launch Essentials

Wallet Improvements
	•	UI/UX Polish
	•	Replace all remaining BTC references with ITC.
	•	Splash screen & dark/light theme branding.
	•	Backup UX
	•	Improved seed backup & restore flow.
	•	In-app seed verification.
	•	Fee Policy
	•	Create simple dynamic fee estimator.
	•	Add mempool-based fee slider.

Web Wallet & SDK
	•	Web Wallet
	•	Watch-only wallet interface.
	•	PSBT & cold signing flow.
	•	TypeScript SDK
	•	ElectrumX helper library for external integrations.

Monitoring & Analytics
	•	Public status page (uptime, node height, fees).
	•	Traffic metrics (Grafana dashboards).

⸻

P2: Future Improvements
	•	Lightning (LSP) integration for instant payments.
	•	Hardware Wallet Support (HWI).
	•	Testnet & Faucet.
	•	Advanced Multisig & Miniscript.
	•	Community Developer Docs.
	•	CI/CD
	•	GitHub Actions for automatic APK builds.
	•	Automated tests & linting pipeline.

⸻

Legend:
	•	P0: Must-have for initial public launch.
	•	P1: Essential improvements right after launch.
	•	P2: Nice-to-have features for long-term growth.

⸻

Next Step: Review and adjust this board to match current sprint priorities, then break down each checkbox into actionable GitHub issues.
