# Ambassador Meeting Capacity Planning

The ambassador meeting hub now enforces explicit limits so you can control how many simultaneous collaboration sessions run on a single deployment and understand the resource footprint those sessions require.

## Configuration knobs

| Variable | Default | Description |
| --- | --- | --- |
| `MEETING_MAX_ROOMS` | `25` | Maximum number of concurrent meeting rooms that can exist at once. Set to `0` or omit to allow unlimited rooms (not recommended without extra monitoring). |
| `MEETING_MAX_PARTICIPANTS` | `12` | Maximum number of ambassadors that may join a single room. Set to `0` or omit for no per-room cap. |

Both settings are read at startup. Any non-positive value is treated as “no limit.”

## Runtime visibility

Authenticated ambassadors can call `GET /api/meetings/metrics` to inspect live usage. The response looks like:

```json
{
  "ok": true,
  "metrics": {
    "rooms_active": 3,
    "rooms_limit": 25,
    "rooms_available": 22,
    "participants_active": 18,
    "participants_per_room_limit": 12,
    "largest_room": 8,
    "estimated_total_capacity": 300
  }
}
```

The front-end shows the same information inside the meeting hub and automatically prevents more users from joining when the configured limits are reached.

## Resource expectations

The FastAPI server only handles chat and WebRTC signalling—media streams travel peer-to-peer—so CPU demand is light. Each active participant occupies a single `MeetingParticipant` record (one WebSocket reference plus two short strings), so the default ceiling of 25 rooms × 12 ambassadors ≈ 300 live attendees keeps memory overhead well under a few megabytes.

Provision at least one dedicated vCPU and ~512 MB of RAM for the ambassador portal process to maintain headroom for bursts and background tasks. Increase memory if you raise the limits or expect heavy concurrent chat traffic. Use the metrics endpoint above to track peak usage and tune the limits before scaling out.
