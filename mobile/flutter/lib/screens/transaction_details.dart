import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class TransactionDetailsScreen extends StatefulWidget {
  final String txid;
  const TransactionDetailsScreen({required this.txid});

  @override
  _TransactionDetailsScreenState createState() => _TransactionDetailsScreenState();
}

class _TransactionDetailsScreenState extends State<TransactionDetailsScreen> {
  Map<String, dynamic>? details;

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    final res = await http.get(Uri.parse('https://example.com/api/transactions/${widget.txid}'));
    setState(() {
      details = jsonDecode(res.body);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (details == null) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
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
        appBar: AppBar(title: const Text('Transaction Details')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('TxID: ${details!['txid']}'),
              Text('Height: ${details!['height']}'),
              ...details!.entries
                  .where((e) => e.key != 'txid' && e.key != 'height')
                  .map((e) => Text('${e.key}: ${e.value}')),
            ],
          ),
        ),
      ),
    );
  }
}
