import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class TransferScreen extends StatefulWidget {
  @override
  _TransferScreenState createState() => _TransferScreenState();
}

class _TransferScreenState extends State<TransferScreen> {
  String address = '';
  String amount = '';

  Future<void> send() async {
    final parsedAmount = (double.parse(amount) * 1e8).round();
    await http.post(
      Uri.parse('https://example.com/api/transfer'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'address': address, 'amount': parsedAmount}),
    );
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Success')));
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
        appBar: AppBar(title: const Text('Transfer')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              TextField(
                decoration: const InputDecoration(labelText: 'Public Address'),
                onChanged: (v) => setState(() => address = v),
              ),
              const SizedBox(height: 12),
              TextField(
                decoration: const InputDecoration(labelText: 'Amount'),
                keyboardType: TextInputType.number,
                onChanged: (v) => setState(() => amount = v),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: send,
                child: const Text('Send'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
