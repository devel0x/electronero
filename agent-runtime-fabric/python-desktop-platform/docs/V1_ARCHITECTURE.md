# V1 Architecture Diagram

```text
+---------------------------------------------------------------+
|                         PyDesk App Process                    |
|                                                               |
|  +----------------------+        JS Bridge RPC                |
|  |  Embedded WebView    | <-------------------------------->  |
|  |  (React/Vite UI)     |                                      |
|  +----------------------+                                      |
|             |                                                 |
|             v                                                 |
|  +----------------------+    permission checks + audit        |
|  | Python Bridge Layer  | ---------------------------------+  |
|  +----------------------+                                  |  |
|      |         |         \                                 |  |
|      v         v          v                                |  |
|  File API   Clipboard   Notifications                       |  |
|      |                                                   logs |
|      +---------------------> local data dir                 |  |
|                                                               |
+---------------------------------------------------------------+
```

## Design decisions
- Single process for V1 to minimize orchestration overhead.
- Explicit bridge methods to avoid unsafe generic command execution.
- TOML manifest controls permissions and build behavior.
