import React, { useEffect, useState } from 'react';
import { View, Text, Button, FlatList, TouchableOpacity, StyleSheet } from 'react-native';

export default function Home({ navigation, route }) {
  const [balance, setBalance] = useState(null);
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    if (route.params) {
      setBalance(route.params.balance);
      setTransactions(route.params.transactions);
    } else {
      fetch('https://example.com/api/balance')
        .then(res => res.json())
        .then(data => setBalance(data.balance))
        .catch(err => console.error(err));

      fetch('https://example.com/api/transactions')
        .then(res => res.json())
        .then(data => setTransactions(data.transactions))
        .catch(err => console.error(err));
    }
  }, [route.params]);

  return (
    <View style={styles.container}>
      <Text style={styles.balanceLabel}>Balance:</Text>
      <Text style={styles.balance}>{balance}</Text>
      <Button title="Transfer" onPress={() => navigation.navigate('Transfer')} />
      <FlatList
        data={transactions}
        keyExtractor={(item) => item.txid}
        renderItem={({ item }) => (
          <TouchableOpacity onPress={() => navigation.navigate('TransactionDetails', { txid: item.txid })}>
            <View style={styles.txItem}>
              <Text>{item.txid}</Text>
              <Text>{item.amount}</Text>
            </View>
          </TouchableOpacity>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16
  },
  balanceLabel: {
    fontWeight: 'bold'
  },
  balance: {
    marginBottom: 16
  },
  txItem: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderColor: '#ccc'
  }
});
