import 'package:flutter/material.dart';
import 'screens/sign_in.dart';
import 'screens/home.dart';
import 'screens/transfer.dart';
import 'screens/transaction_details.dart';

void main() {
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Mobile App',
      theme: ThemeData(
        primarySwatch: Colors.blue,
      ),
      initialRoute: '/',
      routes: {
        '/': (context) => SignInScreen(),
        '/home': (context) => HomeScreen(),
        '/transfer': (context) => TransferScreen(),
      },
      onGenerateRoute: (settings) {
        if (settings.name == '/details') {
          final txid = settings.arguments as String;
          return MaterialPageRoute(
            builder: (context) => TransactionDetailsScreen(txid: txid),
          );
        }
        return null;
      },
    );
  }
}
