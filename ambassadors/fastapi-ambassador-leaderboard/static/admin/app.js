import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import Chart from "https://esm.sh/chart.js@4.4.7/auto";

const fetchJSON = async (url, options = {}) => {
  const finalOptions = {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(options.headers || {}),
    },
    ...options,
  };
  const response = await fetch(url, finalOptions);
  const text = await response.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch (err) {
      console.warn("Failed to parse JSON response from", url, err);
    }
  }
  if (!response.ok || (data && data.ok === false)) {
    const message = data?.error || response.statusText || "Request failed";
    const error = new Error(message);
    error.response = response;
    error.data = data;
    throw error;
  }
  return data ?? { ok: response.ok };
};

const postForm = async (url, payload = {}) => {
  const formData = new FormData();
  Object.entries(payload).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined && item !== null) {
          formData.append(key, item);
        }
      });
    } else if (value !== undefined && value !== null) {
      formData.append(key, value);
    }
  });
  return fetchJSON(url, { method: "POST", body: formData });
};

const useGhostKey = () => {
  const [ghostKey, setGhostKey] = useState(() =>
    window.localStorage.getItem("ambassador:ghost") || ""
  );
  useEffect(() => {
    window.localStorage.setItem("ambassador:ghost", ghostKey);
  }, [ghostKey]);
  return [ghostKey, setGhostKey];
};

const FlashMessage = ({ flash, onDismiss }) => {
  if (!flash) return null;
  return (
    <div
      className={`alert alert-${flash.type} alert-dismissible fade show`}
      role="alert"
    >
      {flash.message}
      <button
        type="button"
        className="btn-close"
        aria-label="Close"
        onClick={onDismiss}
      ></button>
    </div>
  );
};

const SectionCard = ({ id, title, actions, children }) => (
  <section id={id} className="admin-card p-4 mb-4">
    <div className="d-flex flex-wrap justify-content-between align-items-center gap-3 mb-3">
      <div>
        <div className="section-title">{title}</div>
      </div>
      {actions ? <div className="section-actions">{actions}</div> : null}
    </div>
    {children}
  </section>
);

const LoadingState = ({ text = "Loading data..." }) => (
  <div className="d-flex justify-content-center align-items-center py-5">
    <div className="spinner-border text-info me-3" role="status"></div>
    <span className="text-muted">{text}</span>
  </div>
);

const MaintenanceCard = ({ maintenanceEnabled, onToggle, pending }) => {
  return (
    <SectionCard
      id="maintenance"
      title="Maintenance Mode"
      actions={
        <div className="form-check form-switch text-nowrap">
          <input
            className="form-check-input"
            type="checkbox"
            role="switch"
            id="maintenance-toggle"
            checked={maintenanceEnabled}
            disabled={pending}
            onChange={(event) => onToggle(event.target.checked)}
          />
          <label className="form-check-label ms-2" htmlFor="maintenance-toggle">
            {maintenanceEnabled ? "Enabled" : "Disabled"}
          </label>
        </div>
      }
    >
      <p className="mb-0 text-light">
        {maintenanceEnabled
          ? "Ambassador dashboards are paused. Toggle off to restore access."
          : "Enable maintenance to temporarily pause ambassador access while you perform updates."}
      </p>
    </SectionCard>
  );
};

const AnalyticsOverview = ({ analytics }) => {
  const chartRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!analytics) return;
    const growth = Array.isArray(analytics.user_growth)
      ? analytics.user_growth
      : [];
    if (!canvasRef.current) return;

    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    if (!growth.length) return;

    const ctx = canvasRef.current.getContext("2d");
    chartRef.current = new Chart(ctx, {
      type: "line",
      data: {
        labels: growth.map((item) => item.date),
        datasets: [
          {
            label: "Total Users",
            data: growth.map((item) => item.count),
            tension: 0.35,
            fill: true,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            pointBackgroundColor: "#38bdf8",
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: {
            ticks: { color: "#cbd5f5" },
            grid: { color: "rgba(148, 163, 184, 0.1)" },
          },
          y: {
            ticks: { color: "#cbd5f5", precision: 0 },
            grid: { color: "rgba(148, 163, 184, 0.1)" },
            beginAtZero: true,
          },
        },
      },
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
    };
  }, [analytics]);

  if (!analytics) {
    return (
      <SectionCard id="analytics" title="Analytics Overview">
        <p className="text-muted mb-0">Analytics will appear once data is available.</p>
      </SectionCard>
    );
  }

  const visitorDetails = Array.isArray(analytics.visitor_details)
    ? analytics.visitor_details
    : [];
  const locations = Array.isArray(analytics.top_locations)
    ? analytics.top_locations
    : [];

  return (
    <SectionCard id="analytics" title="Analytics Overview">
      <div className="row g-3 mb-3">
        <div className="col-sm-6 col-lg-3">
          <div className="card bg-transparent border-secondary h-100">
            <div className="card-body">
              <p className="text-uppercase small text-muted mb-1">Total Visits</p>
              <div className="fs-4 fw-semibold text-light">
                {analytics.total_visits ?? 0}
              </div>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card bg-transparent border-secondary h-100">
            <div className="card-body">
              <p className="text-uppercase small text-muted mb-1">Unique Visitors</p>
              <div className="fs-4 fw-semibold text-light">
                {analytics.unique_visitors ?? 0}
              </div>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card bg-transparent border-secondary h-100">
            <div className="card-body">
              <p className="text-uppercase small text-muted mb-1">Total Users</p>
              <div className="fs-4 fw-semibold text-light">
                {analytics.total_users ?? 0}
              </div>
            </div>
          </div>
        </div>
        <div className="col-sm-6 col-lg-3">
          <div className="card bg-transparent border-secondary h-100">
            <div className="card-body">
              <p className="text-uppercase small text-muted mb-1">Tracked Locations</p>
              <div className="fs-4 fw-semibold text-light">
                {locations.length}
              </div>
            </div>
          </div>
        </div>
      </div>
      <div className="row g-4">
        <div className="col-lg-8">
          <div className="card bg-transparent border-secondary">
            <div className="card-body">
              <div className="section-title mb-2">Weekly User Growth</div>
              <canvas ref={canvasRef} height="160" />
            </div>
          </div>
        </div>
        <div className="col-lg-4">
          <div className="card bg-transparent border-secondary h-100">
            <div className="card-body">
              <div className="section-title mb-2">Top Locations</div>
              <ul className="list-unstyled mb-0 small">
                {locations.length ? (
                  locations.map((loc, idx) => (
                    <li key={`${loc.location}-${idx}`} className="d-flex justify-content-between">
                      <span>{loc.location}</span>
                      <span className="text-muted">{loc.count}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-muted">No location data yet.</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      </div>
      <div className="mt-4">
        <div className="section-title mb-2">Recent Visitors</div>
        <div className="table-responsive">
          <table className="table table-dark table-striped table-sm align-middle mb-0">
            <thead>
              <tr>
                <th scope="col">IP</th>
                <th scope="col">Label</th>
                <th scope="col" className="text-center">Visits</th>
                <th scope="col">Last Seen</th>
                <th scope="col">Last Path</th>
              </tr>
            </thead>
            <tbody>
              {visitorDetails.length ? (
                visitorDetails.map((visitor) => (
                  <tr key={`${visitor.ip}-${visitor.last_seen}`}>
                    <td><code>{visitor.ip}</code></td>
                    <td>{visitor.label || "—"}</td>
                    <td className="text-center">{visitor.count}</td>
                    <td className="small">{visitor.last_seen}</td>
                    <td className="small text-break">{visitor.last_path || "—"}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="5" className="text-center text-muted py-3">
                    No visitor data captured yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {analytics.total_visitors ? (
          <p className="small text-muted mt-2 mb-0">
            Showing {(analytics.page - 1) * analytics.limit + 1} –
            {Math.min(analytics.page * analytics.limit, analytics.total_visitors)} of
            {analytics.total_visitors} visitors.
          </p>
        ) : null}
      </div>
    </SectionCard>
  );
};

const GhostKeyInput = ({ ghostKey, onChange }) => (
  <SectionCard
    id="ghost"
    title="Session Secrets"
    actions={
      <div className="d-flex gap-2 align-items-center">
        <span className="badge badge-ghost">GHOST Key</span>
        <input
          type="password"
          className="form-control form-control-sm"
          style={{ minWidth: "16rem" }}
          placeholder="Enter ghost key for protected actions"
          value={ghostKey}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    }
  >
    <p className="small text-muted mb-0">
      The ghost key is cached in your browser so you can quickly perform protected
      actions like guardian toggles, score pad adjustments, and transfer resets.
    </p>
  </SectionCard>
);

const StatusPill = ({ label, className = "" }) => (
  <span className={`status-pill ${className}`}>{label}</span>
);

const WalletCard = ({
  wallet,
  onUpdateTelegram,
  onUpdateEmail,
  onUpdatePad,
  onResetPad,
  onToggleGuardian,
  ghostKey,
  setGhostKey,
}) => {
  const [telegram, setTelegram] = useState(wallet.telegram || "");
  const [emailInput, setEmailInput] = useState(wallet.email || "");
  const [padInput, setPadInput] = useState(wallet.pad ?? 0);
  useEffect(() => setTelegram(wallet.telegram || ""), [wallet.telegram]);
  useEffect(() => setEmailInput(wallet.email || ""), [wallet.email]);
  useEffect(() => setPadInput(wallet.pad ?? 0), [wallet.pad]);

  const handleGuardianToggle = () => {
    if (!ghostKey) {
      const key = window.prompt("Enter ghost key to toggle guardian status", ghostKey || "");
      if (key === null) return;
      setGhostKey(key);
      onToggleGuardian(wallet.email, !wallet.guardian, key);
    } else {
      onToggleGuardian(wallet.email, !wallet.guardian, ghostKey);
    }
  };

  const handleResetPad = () => {
    if (!ghostKey) {
      const key = window.prompt("Enter ghost key to reset score pad", ghostKey || "");
      if (key === null) return;
      setGhostKey(key);
      onResetPad(wallet.email, key);
    } else {
      onResetPad(wallet.email, ghostKey);
    }
  };

  return (
    <div className={`wallet-card p-3 h-100 ${wallet.active ? "active" : "inactive"}`}>
      <div className="d-flex justify-content-between flex-wrap gap-2 mb-2">
        <div>
          <h5 className="mb-1">{wallet.email}</h5>
          <div className="d-flex flex-wrap gap-2">
            <StatusPill className={wallet.active ? "active" : "inactive"}>
              {wallet.active ? "Active" : "Inactive"}
            </StatusPill>
            {wallet.verified ? (
              <StatusPill className="bg-success-subtle text-success-emphasis">
                Verified
              </StatusPill>
            ) : null}
            {wallet.guardian ? (
              <StatusPill className="guardian">Guardian</StatusPill>
            ) : null}
          </div>
        </div>
        <div className="text-end">
          <div className="small text-muted">Points</div>
          <div className="fs-5 fw-semibold">{wallet.points?.toLocaleString?.() ?? wallet.points}</div>
          <div className="small text-muted mt-1">Pending Reward</div>
          <div className="fw-semibold">{wallet.pending_reward}</div>
        </div>
      </div>
      <div className="small text-muted mb-2">Wallet</div>
      <div className="d-flex align-items-center gap-2 mb-3">
        <code className="text-break flex-grow-1">{wallet.wallet || "—"}</code>
        {wallet.telegram ? (
          <a
            href={wallet.tg_link || `https://t.me/${wallet.telegram.replace(/^@/, "")}`}
            className="btn btn-sm btn-outline-light"
            target="_blank"
            rel="noopener noreferrer"
          >
            {wallet.telegram}
          </a>
        ) : (
          <span className="badge text-bg-secondary">No Telegram</span>
        )}
      </div>
      <div className="d-flex flex-column gap-2">
        <div className="input-group input-group-sm">
          <span className="input-group-text">Telegram</span>
          <input
            type="text"
            className="form-control"
            value={telegram}
            onChange={(event) => setTelegram(event.target.value)}
          />
          <button
            className="btn btn-outline-light"
            onClick={() => onUpdateTelegram(wallet.email, telegram)}
          >
            Save
          </button>
        </div>
        <div className="input-group input-group-sm">
          <span className="input-group-text">Email</span>
          <input
            type="email"
            className="form-control"
            value={emailInput}
            onChange={(event) => setEmailInput(event.target.value)}
          />
          <button
            className="btn btn-outline-light"
            onClick={() => onUpdateEmail(wallet.email, emailInput)}
          >
            Update
          </button>
        </div>
        <div className="input-group input-group-sm">
          <span className="input-group-text">Score Pad</span>
          <input
            type="number"
            step="1"
            className="form-control"
            value={padInput}
            onChange={(event) => setPadInput(event.target.value)}
          />
          <button
            className="btn btn-outline-light"
            onClick={() => onUpdatePad(wallet.email, padInput)}
          >
            Apply
          </button>
          <button className="btn btn-outline-warning" onClick={handleResetPad}>
            Reset
          </button>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          <button className="btn btn-sm btn-outline-info" onClick={handleGuardianToggle}>
            {wallet.guardian ? "Deactivate Guardian" : "Make Guardian"}
          </button>
          <div className="badge text-bg-dark">Verified Posts: {wallet.verified_posts ?? 0}</div>
        </div>
      </div>
    </div>
  );
};

const WalletSection = ({
  data,
  ghostKey,
  setGhostKey,
  onUpdateTelegram,
  onUpdateEmail,
  onUpdatePad,
  onResetPad,
  onToggleGuardian,
  onValidateWallets,
  validationResult,
  onActivityReset,
  onPadBoost,
  onPadSlash,
  onPadResetAll,
  onExport,
}) => {
  const [filter, setFilter] = useState("");
  const wallets = data.wallets || [];
  const active = data.wallets_active || [];
  const inactive = data.wallets_inactive || [];

  const filteredWallets = useMemo(() => {
    if (!filter.trim()) return { active, inactive };
    const query = filter.trim().toLowerCase();
    const filterGroup = (group) =>
      group.filter((wallet) =>
        [wallet.email, wallet.telegram, wallet.wallet]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query))
      );
    return {
      active: filterGroup(active),
      inactive: filterGroup(inactive),
    };
  }, [filter, active, inactive]);

  const requireGhost = (action, message) => {
    if (ghostKey) {
      action(ghostKey);
      return;
    }
    const key = window.prompt(message, ghostKey || "");
    if (key === null) return;
    setGhostKey(key);
    action(key);
  };

  return (
    <SectionCard
      id="wallets"
      title="Wallet Addresses"
      actions={
        <div className="d-flex flex-wrap gap-2">
          <input
            type="search"
            className="form-control form-control-sm"
            placeholder="Filter by email, wallet, or telegram"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            style={{ minWidth: "18rem" }}
          />
          <button className="btn btn-sm btn-outline-light" onClick={onValidateWallets}>
            Validate Wallets
          </button>
          <button
            className="btn btn-sm btn-outline-info"
            onClick={() =>
              requireGhost(
                onActivityReset,
                "Ghost key required to reset weekly activity"
              )
            }
          >
            Reset Activity
          </button>
          <div className="btn-group btn-group-sm">
            <button
              className="btn btn-outline-light"
              onClick={() => onExport("json")}
            >
              Export JSON
            </button>
            <button
              className="btn btn-outline-light"
              onClick={() => onExport("csv")}
            >
              Export CSV
            </button>
          </div>
          <div className="btn-group btn-group-sm">
            <button
              className="btn btn-outline-success"
              onClick={() =>
                requireGhost(
                  (key) => onPadBoost(key),
                  "Ghost key required to boost active ambassadors"
                )
              }
            >
              Boost Active (+1000)
            </button>
            <button
              className="btn btn-outline-danger"
              onClick={() =>
                requireGhost(
                  (key) => onPadSlash(key),
                  "Ghost key required to slash inactive ambassadors"
                )
              }
            >
              Slash Inactive
            </button>
            <button
              className="btn btn-outline-warning"
              onClick={() =>
                requireGhost(
                  (key) => onPadResetAll(key),
                  "Ghost key required to reset all score pads"
                )
              }
            >
              Reset All Pads
            </button>
          </div>
        </div>
      }
    >
      <div className="d-flex flex-wrap gap-2 mb-3">
        <span className="badge text-bg-success">Active {active.length}</span>
        <span className="badge text-bg-secondary">Inactive {inactive.length}</span>
        <span className="badge bg-light text-dark">Total {wallets.length}</span>
      </div>
      {validationResult ? (
        <div className="alert alert-warning">
          <div className="fw-semibold mb-2">Invalid Wallets</div>
          {validationResult.length ? (
            <ul className="mb-0 small">
              {validationResult.map((entry) => (
                <li key={`${entry.email}-${entry.wallet}`}>
                  {entry.email} – {entry.wallet || "Missing"}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mb-0">All stored wallets validated successfully.</p>
          )}
        </div>
      ) : null}
      {([filteredWallets.active.length, filteredWallets.inactive.length].every(
        (count) => count === 0
      ) && filter.trim()) ? (
        <p className="text-muted">No wallets match your filter.</p>
      ) : null}
      {["Active Users", "Inactive Users"].map((label, idx) => {
        const group = idx === 0 ? filteredWallets.active : filteredWallets.inactive;
        if (!group.length) return null;
        return (
          <div key={label} className="mb-4">
            <h2 className="h6 text-uppercase mb-3">{label} ({group.length})</h2>
            <div className="row row-cols-1 row-cols-lg-2 g-3">
              {group.map((wallet) => (
                <div className="col" key={wallet.email}>
                  <WalletCard
                    wallet={wallet}
                    ghostKey={ghostKey}
                    setGhostKey={setGhostKey}
                    onUpdateTelegram={onUpdateTelegram}
                    onUpdateEmail={onUpdateEmail}
                    onUpdatePad={onUpdatePad}
                    onResetPad={onResetPad}
                    onToggleGuardian={onToggleGuardian}
                  />
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </SectionCard>
  );
};

const PostsSection = ({ posts, onAction }) => {
  const [selected, setSelected] = useState(() => new Set());

  useEffect(() => {
    setSelected(new Set());
  }, [posts]);

  const toggleItem = (key) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const selectUser = (email, entries) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const keys = entries.map((entry) => `${email}||${entry.url}`);
      const allSelected = keys.every((key) => next.has(key));
      keys.forEach((key) => {
        if (allSelected) {
          next.delete(key);
        } else {
          next.add(key);
        }
      });
      return next;
    });
  };

  const handleBulk = (mode) => {
    if (mode === "verify_all") {
      onAction(() => postForm("/admin/posts/verify", { verify_all: "1" }), "Verified all pending posts");
      return;
    }
    const payload = { selected: Array.from(selected) };
    if (!payload.selected.length) return;
    const endpoint =
      mode === "verify_selected"
        ? "/admin/posts/verify"
        : "/admin/posts/reject-selected";
    onAction(
      () => postForm(endpoint, payload),
      mode === "verify_selected" ? "Verified selected posts" : "Rejected selected posts"
    );
  };

  const verifySingle = (email, url) =>
    onAction(
      () => postForm("/admin/posts/verify", { email, url }),
      "Post verified"
    );

  const rejectSingle = (email, url) =>
    onAction(
      () => postForm("/admin/posts/reject", { email, url }),
      "Post rejected"
    );

  const groups = Object.entries(posts || {});

  return (
    <SectionCard
      id="posts"
      title="Submitted Posts"
      actions={
        <div className="btn-group btn-group-sm">
          <button className="btn btn-outline-light" onClick={() => handleBulk("verify_all")}>
            Verify All
          </button>
          <button
            className="btn btn-outline-success"
            onClick={() => handleBulk("verify_selected")}
            disabled={!selected.size}
          >
            Verify Selected
          </button>
          <button
            className="btn btn-outline-danger"
            onClick={() => handleBulk("reject_selected")}
            disabled={!selected.size}
          >
            Reject Selected
          </button>
        </div>
      }
    >
      {groups.length ? (
        groups.map(([email, entry]) => (
          <div className="wallet-card mb-3" key={email}>
            <div className="p-3">
              <div className="d-flex flex-wrap justify-content-between align-items-start gap-2 mb-2">
                <div>
                  <h5 className="mb-0">{email}</h5>
                  <div className="small text-muted">
                    Telegram: {entry.telegram || "—"} · Pending posts: {entry.count}
                  </div>
                </div>
                <button
                  className="btn btn-sm btn-outline-light"
                  onClick={() => selectUser(email, entry.urls || [])}
                >
                  Toggle All
                </button>
              </div>
              <div className="table-responsive">
                <table className="table table-dark table-striped table-sm align-middle mb-0">
                  <tbody>
                    {(entry.urls || []).map((post) => {
                      const key = `${email}||${post.url}`;
                      const isSelected = selected.has(key);
                      return (
                        <tr key={key}>
                          <td className="text-break">
                            <div className="d-flex align-items-center gap-2">
                              <input
                                type="checkbox"
                                className="form-check-input"
                                checked={isSelected}
                                onChange={() => toggleItem(key)}
                              />
                              <a
                                href={post.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="link-light"
                              >
                                {post.url}
                              </a>
                            </div>
                          </td>
                          <td className="text-end">
                            <div className="btn-group btn-group-sm">
                              <button
                                className="btn btn-success"
                                onClick={() => verifySingle(email, post.url)}
                              >
                                Verify
                              </button>
                              <button
                                className="btn btn-danger"
                                onClick={() => rejectSingle(email, post.url)}
                              >
                                Reject
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        ))
      ) : (
        <p className="text-muted mb-0">No pending posts.</p>
      )}
    </SectionCard>
  );
};

const VerifiedSearch = ({ limit }) => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    const q = query.trim();
    if (!q) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchJSON(`/api/admin/posts/search?q=${encodeURIComponent(q)}`);
      if (data?.ok) {
        setResults(data.results || []);
        setCount(data.count || 0);
      } else {
        throw new Error(data?.error || "Search failed");
      }
    } catch (err) {
      setError(err.message || "Failed to search");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SectionCard id="verified-search" title="Verified Link Lookup">
      <form className="row g-2 align-items-end" onSubmit={handleSubmit}>
        <div className="col-md-9 col-lg-10">
          <label className="form-label small text-uppercase">
            Paste part of a verified link
          </label>
          <input
            type="search"
            className="form-control"
            placeholder="https://x.com/..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="col-md-3 col-lg-2">
          <button className="btn btn-primary w-100" disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>
      <p className="small text-muted mt-2">
        Returns up to {limit} matching verified submissions.
      </p>
      {error ? <div className="alert alert-danger py-2">{error}</div> : null}
      <div className="mt-3">
        {results.length ? (
          <div className="list-group">
            {results.map((entry) => (
              <a
                key={`${entry.email}-${entry.url}`}
                href={entry.url}
                className="list-group-item list-group-item-action bg-transparent text-light border-secondary"
                target="_blank"
                rel="noopener noreferrer"
              >
                <div className="fw-semibold">{entry.url}</div>
                <div className="small text-muted">
                  {entry.email} · {entry.telegram || "No Telegram"}
                </div>
              </a>
            ))}
          </div>
        ) : (
          <p className="text-muted mb-0">No results yet.</p>
        )}
      </div>
      {count > results.length ? (
        <p className="small text-muted mt-2 mb-0">
          Showing first {results.length} matches out of {count}.
        </p>
      ) : null}
    </SectionCard>
  );
};

const TasksSection = ({ tasks, taskLabels, onAction }) => {
  const [selected, setSelected] = useState(() => new Set());

  useEffect(() => {
    setSelected(new Set());
  }, [tasks]);

  const toggle = (key) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const selectUser = (email, entries) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const keys = entries.map(([taskId]) => `${email}||${taskId}`);
      const allSelected = keys.every((key) => next.has(key));
      keys.forEach((key) => {
        if (allSelected) next.delete(key);
        else next.add(key);
      });
      return next;
    });
  };

  const handleBulk = (action) => {
    if (action === "verify_all") {
      onAction(
        () => postForm("/admin/tasks/bulk", { action: "verify_all" }),
        "Verified all pending tasks"
      );
      return;
    }
    const payload = { selected: Array.from(selected), action };
    if (!payload.selected.length) return;
    onAction(
      () => postForm("/admin/tasks/bulk", payload),
      action === "verify_selected"
        ? "Verified selected tasks"
        : "Deleted selected tasks"
    );
  };

  const verifySingle = (email, taskId) =>
    onAction(
      () => postForm("/admin/tasks/verify", { email, task_id: taskId }),
      "Task verified"
    );
  const destroySingle = (email, taskId) =>
    onAction(
      () => postForm("/admin/tasks/destroy", { email, task_id: taskId }),
      "Task removed"
    );

  const groups = Object.entries(tasks || {});

  return (
    <SectionCard
      id="tasks"
      title="Task Submissions"
      actions={
        <div className="btn-group btn-group-sm">
          <button className="btn btn-outline-light" onClick={() => handleBulk("verify_all")}>
            Verify All
          </button>
          <button
            className="btn btn-outline-success"
            onClick={() => handleBulk("verify_selected")}
            disabled={!selected.size}
          >
            Verify Selected
          </button>
          <button
            className="btn btn-outline-danger"
            onClick={() => handleBulk("destroy_selected")}
            disabled={!selected.size}
          >
            Delete Selected
          </button>
        </div>
      }
    >
      {groups.length ? (
        groups.map(([email, mapping]) => {
          const entries = Object.entries(mapping || {});
          if (!entries.length) return null;
          return (
            <div className="wallet-card mb-3" key={email}>
              <div className="p-3">
                <div className="d-flex justify-content-between align-items-center mb-2">
                  <h5 className="mb-0">{email}</h5>
                  <button
                    className="btn btn-sm btn-outline-light"
                    onClick={() => selectUser(email, entries)}
                  >
                    Toggle All
                  </button>
                </div>
                <div className="table-responsive">
                  <table className="table table-dark table-striped table-sm align-middle mb-0">
                    <tbody>
                      {entries.map(([taskId, status]) => {
                        const key = `${email}||${taskId}`;
                        const label = taskLabels?.[taskId] || taskId;
                        const isSelected = selected.has(key);
                        return (
                          <tr key={key}>
                            <td>
                              <div className="d-flex gap-2 align-items-start">
                                <input
                                  type="checkbox"
                                  className="form-check-input mt-1"
                                  checked={isSelected}
                                  onChange={() => toggle(key)}
                                />
                                <div>
                                  <div className="fw-semibold">{label}</div>
                                  <div className="small text-muted">Status: {status}</div>
                                </div>
                              </div>
                            </td>
                            <td className="text-end">
                              <div className="btn-group btn-group-sm">
                                <button
                                  className="btn btn-success"
                                  onClick={() => verifySingle(email, taskId)}
                                >
                                  Verify
                                </button>
                                <button
                                  className="btn btn-danger"
                                  onClick={() => destroySingle(email, taskId)}
                                >
                                  Delete
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          );
        })
      ) : (
        <p className="text-muted mb-0">No pending tasks.</p>
      )}
    </SectionCard>
  );
};

const ProposalCard = ({ proposal, onAction }) => {
  const [fundingWallet, setFundingWallet] = useState(
    proposal.funding_wallet || ""
  );

  useEffect(() => {
    setFundingWallet(proposal.funding_wallet || "");
  }, [proposal.funding_wallet]);

  return (
    <div className="wallet-card p-3">
      <h5 className="mb-1">{proposal.title}</h5>
      <p className="mb-2">{proposal.content}</p>
      <div className="small text-muted mb-3">
        {proposal.email} · {proposal.telegram || "No Telegram"} · {proposal.wallet}
      </div>
      <div className="d-flex flex-column flex-md-row gap-2">
        <div className="input-group input-group-sm">
          <span className="input-group-text">Funding Wallet</span>
          <input
            type="text"
            className="form-control"
            value={fundingWallet}
            onChange={(event) => setFundingWallet(event.target.value)}
          />
        </div>
        <div className="btn-group btn-group-sm">
          <button
            className="btn btn-success"
            onClick={() =>
              onAction(
                () =>
                  postForm("/admin/proposals/verify", {
                    proposal_id: proposal.id,
                    funding_wallet: fundingWallet,
                  }),
                "Proposal approved"
              )
            }
          >
            Approve
          </button>
          <button
            className="btn btn-outline-danger"
            onClick={() =>
              onAction(
                () =>
                  postForm("/admin/proposals/reject", {
                    proposal_id: proposal.id,
                  }),
                "Proposal rejected"
              )
            }
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
};

const ProposalsSection = ({ proposals, onAction }) => {
  if (!proposals?.length) {
    return (
      <SectionCard id="proposals" title="Pending Proposals">
        <p className="text-muted mb-0">No pending proposals.</p>
      </SectionCard>
    );
  }
  return (
    <SectionCard id="proposals" title="Pending Proposals">
      <div className="row g-3">
        {proposals.map((proposal) => (
          <div className="col-12" key={proposal.id}>
            <ProposalCard proposal={proposal} onAction={onAction} />
          </div>
        ))}
      </div>
    </SectionCard>
  );
};

const RecoveriesSection = ({ recoveries, ghostKey, setGhostKey, onReset }) => {
  const handleReset = (email) => {
    if (!ghostKey) {
      const key = window.prompt("Enter ghost key to reset recovery", ghostKey || "");
      if (key === null) return;
      setGhostKey(key);
      onReset(email, key);
    } else {
      onReset(email, ghostKey);
    }
  };

  return (
    <SectionCard id="recoveries" title="Password Recoveries">
      {recoveries?.length ? (
        <ul className="list-group list-group-flush">
          {recoveries.map((entry) => (
            <li
              className="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center"
              key={entry.email}
            >
              <div>
                <div><strong>Email:</strong> {entry.email}</div>
                <div>
                  <strong>Telegram:</strong> {" "}
                  {entry.tg_link ? (
                    <a href={entry.tg_link} target="_blank" rel="noopener noreferrer" className="link-light">
                      {entry.telegram}
                    </a>
                  ) : (
                    entry.telegram || "N/A"
                  )}
                </div>
              </div>
              <div className="d-flex align-items-center gap-2">
                <code>{entry.code}</code>
                <button
                  className="btn btn-success btn-sm"
                  onClick={() => handleReset(entry.email)}
                >
                  Reset
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted mb-0">No recovery requests.</p>
      )}
    </SectionCard>
  );
};

const TransfersSection = ({ transfers, ghostKey, setGhostKey, onReset, onDelete }) => {
  const requireGhost = (action, message) => {
    if (ghostKey) {
      action(ghostKey);
      return;
    }
    const key = window.prompt(message, ghostKey || "");
    if (key === null) return;
    setGhostKey(key);
    action(key);
  };

  return (
    <SectionCard
      id="transfers"
      title="Transfer Ledger"
      actions={
        <div className="btn-group btn-group-sm">
          <button
            className="btn btn-outline-warning"
            onClick={() =>
              requireGhost(onReset, "Ghost key required to zero transfer history")
            }
          >
            Reset Amounts
          </button>
          <button
            className="btn btn-outline-danger"
            onClick={() =>
              requireGhost(onDelete, "Ghost key required to delete transfer history")
            }
          >
            Delete History
          </button>
        </div>
      }
    >
      <div className="table-responsive">
        <table className="table table-dark table-striped table-sm align-middle mb-0">
          <thead>
            <tr>
              <th scope="col">Timestamp (UTC)</th>
              <th scope="col">Source</th>
              <th scope="col">Destination</th>
              <th scope="col" className="text-end">Amount</th>
            </tr>
          </thead>
          <tbody>
            {transfers?.length ? (
              transfers.map((entry, idx) => (
                <tr key={`${entry.timestamp}-${idx}`}>
                  <td className="small">{entry.timestamp?.replace?.("T", " ") || "—"}</td>
                  <td>
                    <div className="fw-semibold">{entry.source_name || entry.source || "—"}</div>
                    {entry.source ? (
                      <div className="small text-muted">{entry.source}</div>
                    ) : null}
                    {entry.source_telegram ? (
                      <div className="small">
                        <a
                          className="link-light"
                          href={`https://t.me/${String(entry.source_telegram).replace(/^@/, "")}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {entry.source_telegram}
                        </a>
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <div className="fw-semibold">{entry.destination_name || entry.destination || "—"}</div>
                    {entry.destination ? (
                      <div className="small text-muted">{entry.destination}</div>
                    ) : null}
                    {entry.destination_telegram ? (
                      <div className="small">
                        <a
                          className="link-light"
                          href={`https://t.me/${String(entry.destination_telegram).replace(/^@/, "")}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {entry.destination_telegram}
                        </a>
                      </div>
                    ) : null}
                  </td>
                  <td className="text-end">{Number(entry.amount || 0).toFixed(2)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="4" className="text-center text-muted py-4">
                  No transfers recorded yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
};

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [flash, setFlash] = useState(null);
  const [maintenancePending, setMaintenancePending] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [ghostKey, setGhostKey] = useGhostKey();

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetchJSON("/api/admin/dashboard");
      if (response?.ok) {
        setData(response.data || {});
      } else {
        throw new Error(response?.error || "Failed to load dashboard");
      }
    } catch (err) {
      if (err?.response?.status === 401) {
        window.location.href = "/admin/login";
        return;
      }
      setError(err.message || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const runAction = useCallback(
    async (action, successMessage) => {
      try {
        await action();
        if (successMessage) {
          setFlash({ type: "success", message: successMessage });
        }
        await loadData();
      } catch (err) {
        if (err?.response?.status === 401) {
          window.location.href = "/admin/login";
          return;
        }
        setFlash({ type: "danger", message: err.message || "Action failed" });
      }
    },
    [loadData]
  );

  const toggleMaintenance = async (nextState) => {
    setMaintenancePending(true);
    try {
      await runAction(
        () => postForm("/admin/maintenance", { enabled: nextState ? "1" : "0" }),
        nextState ? "Maintenance enabled" : "Maintenance disabled"
      );
    } finally {
      setMaintenancePending(false);
    }
  };

  const validateWallets = async () => {
    try {
      const result = await fetchJSON("/api/admin/validate_wallets");
      if (result?.ok) {
        setValidationResult(result.invalid || []);
        if (!result.invalid?.length) {
          setFlash({ type: "success", message: "All wallets are valid." });
        } else {
          setFlash({ type: "warning", message: "Found invalid wallet entries." });
        }
      } else {
        throw new Error(result?.error || "Validation failed");
      }
    } catch (err) {
      setFlash({ type: "danger", message: err.message || "Validation failed" });
    }
  };

  const exportWallets = (format) => {
    if (!ghostKey) {
      const key = window.prompt("Enter ghost key for export", ghostKey || "");
      if (key === null) return;
      setGhostKey(key);
      window.open(`/api/admin/export?fmt=${format}&ghost=${encodeURIComponent(key)}`, "_blank");
      return;
    }
    window.open(
      `/api/admin/export?fmt=${format}&ghost=${encodeURIComponent(ghostKey)}`,
      "_blank"
    );
  };

  if (loading) {
    return (
      <div className="container py-5">
        <LoadingState />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container py-5">
        <div className="alert alert-danger">{error}</div>
        <button className="btn btn-outline-light" onClick={loadData}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <>
      <nav className="navbar navbar-expand-lg navbar-dark admin-navbar">
        <div className="container-fluid">
          <a className="navbar-brand fw-semibold" href="#top">
            Ambassador Admin
          </a>
          <button
            className="navbar-toggler"
            type="button"
            data-bs-toggle="collapse"
            data-bs-target="#adminNav"
            aria-controls="adminNav"
            aria-expanded="false"
            aria-label="Toggle navigation"
          >
            <span className="navbar-toggler-icon"></span>
          </button>
          <div className="collapse navbar-collapse" id="adminNav">
            <ul className="navbar-nav me-auto mb-2 mb-lg-0">
              {["maintenance", "analytics", "recoveries", "wallets", "posts", "verified-search", "tasks", "proposals", "transfers"].map(
                (id) => (
                  <li className="nav-item" key={id}>
                    <a className="nav-link" href={`#${id}`}>
                      {id.replace("-", " ")}
                    </a>
                  </li>
                )
              )}
            </ul>
            <a href="/admin/logout" className="btn btn-outline-light btn-sm">
              Logout
            </a>
          </div>
        </div>
      </nav>
      <main className="container py-4">
        <FlashMessage flash={flash} onDismiss={() => setFlash(null)} />
        <GhostKeyInput ghostKey={ghostKey} onChange={setGhostKey} />
        <MaintenanceCard
          maintenanceEnabled={Boolean(data.maintenance_enabled)}
          onToggle={toggleMaintenance}
          pending={maintenancePending}
        />
        <AnalyticsOverview analytics={data.analytics} />
        <RecoveriesSection
          recoveries={data.recoveries}
          ghostKey={ghostKey}
          setGhostKey={setGhostKey}
          onReset={(email, key) =>
            runAction(
              () => postForm("/admin/recovery/reset", { email, ghost: key }),
              "Recovery reset"
            )
          }
        />
        <WalletSection
          data={data}
          ghostKey={ghostKey}
          setGhostKey={setGhostKey}
          onUpdateTelegram={(email, telegram) =>
            runAction(
              () => postForm("/admin/telegram/update", { email, telegram }),
              "Telegram updated"
            )
          }
          onUpdateEmail={(currentEmail, newEmail) =>
            runAction(
              () => postForm("/admin/email/update", {
                current_email: currentEmail,
                new_email: newEmail,
              }),
              "Email updated"
            )
          }
          onUpdatePad={(email, pad) =>
            runAction(
              () => postForm("/admin/scorepad", { email, pad }),
              "Score pad saved"
            )
          }
          onResetPad={(email, key) =>
            runAction(
              () => postForm("/admin/scorepad/reset", { emails: [email], ghost: key }),
              "Score pad reset"
            )
          }
          onToggleGuardian={(email, enabled, key) =>
            runAction(
              () =>
                postForm("/admin/guardians/toggle", {
                  email,
                  enable: enabled ? "1" : "0",
                  ghost: key,
                }),
              enabled ? "Guardian enabled" : "Guardian disabled"
            )
          }
          onValidateWallets={validateWallets}
          validationResult={validationResult}
          onActivityReset={(key) =>
            runAction(
              () => postForm("/admin/activity/reset", { ghost: key }),
              "Activity reset"
            )
          }
          onPadBoost={(key) =>
            runAction(
              () => postForm("/admin/scorepad/boost", { ghost: key }),
              "Boost applied"
            )
          }
          onPadSlash={(key) =>
            runAction(
              () => postForm("/admin/scorepad/slash", { ghost: key }),
              "Inactive ambassadors slashed"
            )
          }
          onPadResetAll={(key) =>
            runAction(
              () => postForm("/admin/scorepad/reset", { reset_all: "1", ghost: key }),
              "All pads reset"
            )
          }
          onExport={exportWallets}
        />
        <PostsSection posts={data.posts} onAction={runAction} />
        <VerifiedSearch limit={data.verified_search_limit} />
        <TasksSection
          tasks={data.tasks}
          taskLabels={data.task_labels}
          onAction={runAction}
        />
        <ProposalsSection proposals={data.proposals} onAction={runAction} />
        <TransfersSection
          transfers={data.transfers}
          ghostKey={ghostKey}
          setGhostKey={setGhostKey}
          onReset={(key) =>
            runAction(
              () => postForm("/admin/transfers/reset", { ghost: key }),
              "Transfer totals reset"
            )
          }
          onDelete={(key) =>
            runAction(
              () => postForm("/admin/transfers/delete", { ghost: key }),
              "Transfer history deleted"
            )
          }
        />
      </main>
    </>
  );
};

const container = document.getElementById("root");
createRoot(container).render(<Dashboard />);
