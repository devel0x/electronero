package electronero

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
)

// RPCError represents an error returned by the Electronero RPC services.
type RPCError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type rpcRequest struct {
	Jsonrpc string      `json:"jsonrpc"`
	ID      string      `json:"id"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params,omitempty"`
}

type rpcResponse struct {
	Jsonrpc string          `json:"jsonrpc"`
	ID      string          `json:"id"`
	Result  json.RawMessage `json:"result"`
	Error   *RPCError       `json:"error"`
}

// Client provides access to Electronero daemon or wallet RPC endpoints.
type Client struct {
	Endpoint   string
	HTTPClient *http.Client
}

// NewDaemonClient creates a client for communicating with electronerod.
func NewDaemonClient(endpoint string) *Client {
	return &Client{Endpoint: endpoint, HTTPClient: http.DefaultClient}
}

// NewWalletClient creates a client for communicating with electronero-wallet-rpc.
func NewWalletClient(endpoint string) *Client {
	return &Client{Endpoint: endpoint, HTTPClient: http.DefaultClient}
}

// Call invokes a JSON-RPC method on the given service.
func (c *Client) Call(method string, params interface{}, result interface{}) error {
	return c.callPath("/json_rpc", method, params, result)
}

func (c *Client) callPath(path, method string, params interface{}, result interface{}) error {
	reqData := rpcRequest{Jsonrpc: "2.0", ID: "0", Method: method, Params: params}
	b, err := json.Marshal(reqData)
	if err != nil {
		return err
	}
	resp, err := c.HTTPClient.Post(c.Endpoint+path, "application/json", bytes.NewReader(b))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status: %s", resp.Status)
	}
	var rpcResp rpcResponse
	if err := json.NewDecoder(resp.Body).Decode(&rpcResp); err != nil {
		return err
	}
	if rpcResp.Error != nil {
		return fmt.Errorf("RPC error %d: %s", rpcResp.Error.Code, rpcResp.Error.Message)
	}
	if result != nil {
		return json.Unmarshal(rpcResp.Result, result)
	}
	return nil
}

// Do sends a POST request with JSON parameters to a custom RPC path.
func (c *Client) Do(path string, params interface{}, result interface{}) error {
	b, err := json.Marshal(params)
	if err != nil {
		return err
	}
	resp, err := c.HTTPClient.Post(c.Endpoint+path, "application/json", bytes.NewReader(b))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("unexpected status: %s", resp.Status)
	}
	if result != nil {
		return json.NewDecoder(resp.Body).Decode(result)
	}
	return nil
}

// GetBlockCount returns the current height of the blockchain from the daemon.
func (c *Client) GetBlockCount() (uint64, error) {
	var res struct {
		Count uint64 `json:"count"`
	}
	if err := c.Call("getblockcount", nil, &res); err != nil {
		return 0, err
	}
	return res.Count, nil
}

// GetBalance returns the wallet balance for the specified account index.
func (c *Client) GetBalance(accountIndex uint32) (uint64, uint64, error) {
	req := map[string]uint32{"account_index": accountIndex}
	var res struct {
		Balance         uint64 `json:"balance"`
		UnlockedBalance uint64 `json:"unlocked_balance"`
	}
	if err := c.Call("get_balance", req, &res); err != nil {
		return 0, 0, err
	}
	return res.Balance, res.UnlockedBalance, nil
}
