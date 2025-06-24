import React, { useEffect, useState } from 'react';
import { View, Text, Button, FlatList, TouchableOpacity, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function Home({ navigation, route }) {
  const [balance, setBalance] = useState(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [etnxBalance, setEtnxBalance] = useState(0);
  const [etnxpBalance, setEtnxpBalance] = useState(0);
  const [etnxAindex, setEtnxAindex] = useState(0);
  const [etnxpAindex, setEtnxpAindex] = useState(0);
  const [etnxUserId, setEtnxUserId] = useState(0);
  const [etnxpUserId, setEtnxpUserId] = useState(0);
  const [transactions, setTransactions] = useState([]);

  useEffect(() => {
    if (route.params) {
      setPin(route.params.code);
      setEmail(route.params.email);
      setPassword(route.params.password);
      setEtnxUserId(route.params.etnx_user_id);
      setEtnxpUserId(route.params.etnxp_user_id);
      setEtnxAindex(route.params.etnx_aindex);
      setEtnxpAindex(route.params.etnxp_aindex);
      setEtnxBalance(route.params.etnx_balance);
      setEtnxpBalance(route.params.etnxp_balance);
      setTransactions(route.params.transactions);
          const payload = new URLSearchParams();
          payload.append('method', 'getBalances_nohistory');
          payload.append('email', email);
          payload.append('password', password);
          payload.append('code', pin);
          payload.append('coin', 'etnx');
        
          fetch('https://passport.electronero.org/passport/api.php', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: payload.toString()
          })
            .then(res => res.json())
            .then(data => {
              console.log(data);
              if (data.status.success) {
                navigation.navigate('Home', {
                  email: email,
                  password: password,
                  code: pin,
                  etnx_balance: data.data.etnx_balance,
                  etnxp_balance: data.data.etnxp_balance,
                  etnx_aindex: data.data.etnx_aindex,
                  etnxp_aindex: data.data.etnxp_aindex,
                  etnx_user_id: data.data.etnx_uid, 
                  etnxp_user_id: data.data.etnxp_uid, 
                  transactions: []
                });
              }
            })
            .catch(err => console.error(err));
    } else {
          const payload = new URLSearchParams();
          payload.append('method', 'getBalance_webnero');
          payload.append('email', email);
          payload.append('password', password);
          payload.append('code', pin);
        
          fetch('https://passport.electronero.org/passport/api.php', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: payload.toString()
          })
            .then(res => res.json())
            .then(data => {
              console.log(data);
              if (data.status.success) {
                navigation.navigate('Home', {
                  email: email,
                  password: password,
                  code: pin,
                  etnx_balance: data.data.etnx_balance,
                  etnxp_balance: data.data.etnxp_balance,
                  etnx_aindex: data.data.etnx_aindex,
                  etnxp_aindex: data.data.etnxp_aindex,
                  etnx_user_id: data.data.etnx_uid, 
                  etnxp_user_id: data.data.etnxp_uid, 
                  transactions: []
                });
              }
            })
            .catch(err => console.error(err));
    }
  }, [route.params]);

  return (
    <LinearGradient colors={['#FFD700', '#808080', '#000']} style={styles.container}>
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
    </LinearGradient>
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
