import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class SignInScreen extends StatefulWidget {
  @override
  _SignInScreenState createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  String email = '';
  String password = '';
  String pin = '';
  bool showPin = false;

  Future<void> submit() async {
    final response = await http.post(
      Uri.parse('https://example.com/api/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password, 'pin_code': pin}),
    );
    final data = jsonDecode(response.body);
    if (data['success'] == true) {
      Navigator.pushReplacementNamed(
        context,
        '/home',
        arguments: {
          'balance': data['data']['balance'],
          'transactions': data['data']['transactions'],
        },
      );
    }
  }

  Widget buildKey(int? number) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: ElevatedButton(
          onPressed: number == null || pin.length >= 5
              ? null
              : () {
                  setState(() {
                    pin += number.toString();
                  });
                },
          child: Text(number != null ? number.toString() : ''),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.yellow, Colors.grey, Colors.black],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: GestureDetector(
          onTap: () => FocusScope.of(context).unfocus(),
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  TextField(
                    decoration: const InputDecoration(labelText: 'Email'),
                    onChanged: (v) => setState(() => email = v),
                  ),
              const SizedBox(height: 12),
              TextField(
                decoration: const InputDecoration(labelText: 'Password'),
                obscureText: true,
                onChanged: (v) => setState(() => password = v),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: () => setState(() => showPin = true),
                child: const Text('Sign In'),
              ),
              if (showPin) ...[
                const SizedBox(height: 20),
                Text('Enter 5-digit PIN'),
                Text('*' * pin.length),
                const SizedBox(height: 8),
                Column(
                  children: [
                    for (var row in [
                      [1, 2, 3],
                      [4, 5, 6],
                      [7, 8, 9],
                      [null, 0, null]
                    ])
                      Row(
                        children: [for (var n in row) buildKey(n)],
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                ElevatedButton(
                  onPressed: () {
                    setState(() => showPin = false);
                    submit();
                  },
                  child: const Text('Submit'),
                ),
              ]
              ],
            ),
          ),
        ),
      ),
    );
  }
}
