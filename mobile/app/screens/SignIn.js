import React, { useState } from 'react';
import { View, TextInput, Button, Modal, Text, StyleSheet } from 'react-native';

export default function SignIn({ navigation }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPin, setShowPin] = useState(false);

  const handleSignIn = () => {
    setShowPin(true);
  };

  const submitPin = () => {
    const payload = { email, password, pin_code: pin };
    fetch('https://example.com/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          navigation.navigate('Home', {
            balance: data.data.balance,
            transactions: data.data.transactions
          });
        }
      })
      .catch(err => console.error(err));
  };

  return (
    <View style={styles.container}>
      <TextInput
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        style={styles.input}
      />
      <TextInput
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={styles.input}
      />
      <Button title="Sign In" onPress={handleSignIn} />

      <Modal visible={showPin} transparent>
        <View style={styles.modalContainer}>
          <View style={styles.modalContent}>
            <Text>Enter 5-digit PIN</Text>
            <TextInput
              value={pin}
              onChangeText={setPin}
              keyboardType="numeric"
              secureTextEntry
              maxLength={5}
              style={styles.input}
            />
            <Button title="Submit" onPress={submitPin} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    justifyContent: 'center'
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 8,
    marginBottom: 12,
    backgroundColor: 'white'
  },
  modalContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'rgba(0,0,0,0.5)'
  },
  modalContent: {
    backgroundColor: 'white',
    padding: 16,
    borderRadius: 4,
    width: '80%'
  }
});
