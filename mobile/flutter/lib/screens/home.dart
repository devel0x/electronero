import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class HomeScreen extends StatefulWidget {
  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  double? balance;
  List<dynamic> transactions = [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)!.settings.arguments as Map?;
    if (args != null) {
      balance = args['balance'];
      transactions = args['transactions'] ?? [];
    } else {
      loadData();
    }
  }

  Future<void> loadData() async {
    final balRes = await http.get(Uri.parse('https://example.com/api/balance'));
    final txRes = await http.get(Uri.parse('https://example.com/api/transactions'));
    setState(() {
      balance = jsonDecode(balRes.body)['balance'];
      transactions = jsonDecode(txRes.body)['transactions'];
    });
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
        appBar: AppBar(title: const Text('Home')),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            children: [
              Text('Balance: ${balance ?? ''}'),
              const SizedBox(height: 8),
              ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, '/transfer'),
                child: const Text('Transfer'),
              ),
              const SizedBox(height: 8),
              Expanded(
                child: ListView.builder(
                  itemCount: transactions.length,
                  itemBuilder: (context, index) {
                    final tx = transactions[index];
                    return ListTile(
                      title: Text(tx['txid'].toString()),
                      subtitle: Text(tx['amount'].toString()),
                      onTap: () => Navigator.pushNamed(
                        context,
                        '/details',
                        arguments: tx['txid'],
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
