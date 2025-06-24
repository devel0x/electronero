import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function TransactionDetails({ route }) {
  const { txid } = route.params;
  const [details, setDetails] = useState(null);

  useEffect(() => {
    fetch(`https://example.com/api/transactions/${txid}`)
      .then(res => res.json())
      .then(data => setDetails(data))
      .catch(err => console.error(err));
  }, [txid]);

  if (!details) {
    return <Text>Loading...</Text>;
  }

  return (
    <LinearGradient colors={['#FFD700', '#808080', '#000']} style={styles.container}>
      <Text>TxID: {details.txid}</Text>
      <Text>Height: {details.height}</Text>
      {Object.entries(details).map(([key, value]) => (
        key !== 'txid' && key !== 'height' ? <Text key={key}>{`${key}: ${value}`}</Text> : null
      ))}
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16
  }
});
