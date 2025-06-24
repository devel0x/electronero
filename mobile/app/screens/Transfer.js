import React, { useState } from 'react';
import { View, TextInput, Button, Alert, StyleSheet } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function Transfer() {
  const [address, setAddress] = useState('');
  const [amount, setAmount] = useState('');

  const send = () => {
    const parsedAmount = (parseFloat(amount) * 1e8).toFixed(0);
    fetch('https://example.com/api/transfer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ address, amount: parsedAmount })
    })
      .then(res => res.json())
      .then(() => Alert.alert('Success'))
      .catch(err => {
        console.error(err);
        Alert.alert('Error');
      });
  };

  return (
    <LinearGradient colors={['#FFD700', '#808080', '#000']} style={styles.container}>
      <TextInput
        placeholder="Public Address"
        value={address}
        onChangeText={setAddress}
        style={styles.input}
      />
      <TextInput
        placeholder="Amount"
        value={amount}
        onChangeText={setAmount}
        keyboardType="numeric"
        style={styles.input}
      />
      <Button title="Send" onPress={send} />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 8,
    marginBottom: 12
  }
});
