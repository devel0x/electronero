<?php
require_once __DIR__ . '/electronero.php';

$token = getenv('TELEGRAM_TOKEN');
if (!$token) {
    fwrite(STDERR, "TELEGRAM_TOKEN environment variable not set\n");
    exit(1);
}

$apiUrl = "https://api.telegram.org/bot{$token}/";
$rpc = new ElectroneroRPC();

function apiRequest($method, $params = []) {
    global $apiUrl;
    $ch = curl_init($apiUrl . $method);
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
        CURLOPT_POSTFIELDS => json_encode($params),
        CURLOPT_TIMEOUT => 30
    ]);
    $res = curl_exec($ch);
    curl_close($ch);
    return json_decode($res, true);
}

function sendMessage($chatId, $text, array $replyMarkup = []) {
    $payload = [
        'chat_id' => $chatId,
        'text'    => $text
    ];
    if ($replyMarkup) {
        $payload['reply_markup'] = json_encode($replyMarkup);
    }
    apiRequest('sendMessage', $payload);
}

function buildKeyboard(array $methods) {
    $rows = [];
    $chunk = array_chunk($methods, 2);
    foreach ($chunk as $pair) {
        $row = [];
        foreach ($pair as $m) {
            $row[] = '/' . $m;
        }
        $rows[] = $row;
    }
    return [
        'keyboard' => $rows,
        'resize_keyboard' => true
    ];
}

function sendMainMenu($chatId) {
    $menu = [
        'keyboard' => [
            ['/wallet'],
            ['/daemon']
        ],
        'resize_keyboard' => true
    ];
    sendMessage($chatId, "Choose a command group:", $menu);
}

function handleCommand($chatId, $text, $rpc) {
    $text = trim($text);
    if ($text === '/start') {
        sendMessage($chatId, "Welcome to the Electronero bot. Use /wallet or /daemon to view available RPC commands.");
        sendMainMenu($chatId);
        return;
    }
    if ($text === '/menu') {
        sendMainMenu($chatId);
        return;
    }
    if ($text === '/help') {
        $wallet = implode("\n", $rpc->listWalletMethods());
        $daemon = implode("\n", $rpc->listDaemonMethods());
        $msg = "Wallet RPC:\n$wallet\n\nDaemon RPC:\n$daemon\n";
        sendMessage($chatId, $msg);
        return;
    }
    if ($text === '/wallet') {
        $kb = buildKeyboard($rpc->listWalletMethods());
        sendMessage($chatId, 'Wallet RPC methods:', $kb);
        return;
    }
    if ($text === '/daemon') {
        $kb = buildKeyboard($rpc->listDaemonMethods());
        sendMessage($chatId, 'Daemon RPC methods:', $kb);
        return;
    }
    if ($text[0] === '/') {
        $parts = explode(' ', substr($text, 1), 2);
        $method = $parts[0];
        $params = [];
        if (isset($parts[1])) {
            $params = json_decode($parts[1], true);
            if (!is_array($params)) {
                sendMessage($chatId, "Invalid JSON parameters");
                return;
            }
        }
        try {
            $result = $rpc->$method($params);
            sendMessage($chatId, json_encode($result, JSON_PRETTY_PRINT));
        } catch (Exception $e) {
            sendMessage($chatId, 'Error: ' . $e->getMessage());
        }
    }
}

$offset = 0;
while (true) {
    $response = apiRequest('getUpdates', ['timeout' => 30, 'offset' => $offset]);
    if (!isset($response['result'])) {
        sleep(1);
        continue;
    }
    foreach ($response['result'] as $update) {
        $offset = $update['update_id'] + 1;
        if (isset($update['message']['chat']['id']) && isset($update['message']['text'])) {
            handleCommand($update['message']['chat']['id'], $update['message']['text'], $rpc);
        }
    }
}
?>
