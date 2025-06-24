import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';

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
    <View style={styles.container}>
      <Text>TxID: {details.txid}</Text>
      <Text>Height: {details.height}</Text>
      {Object.entries(details).map(([key, value]) => (
        key !== 'txid' && key !== 'height' ? <Text key={key}>{`${key}: ${value}`}</Text> : null
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16
  }
});
