import React, { useState } from 'react';
import { View, TextInput, Button, Modal, Text, StyleSheet, Pressable, TouchableOpacity } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

export default function SignIn({ navigation }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [showPin, setShowPin] = useState(false);

  const handleSignIn = () => {
    setShowPin(true);
  };

  const submitPin = () => {
    const payload = new URLSearchParams();
    payload.append('method', 'login_webnero');
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
        if (data.status == 'success') {
          navigation.navigate('Home', {
            email: email,
            password: password,
            code: pin,
            etnx_balance: 0.00000000,
            etnxp_balance: 0.000000,
            etnx_aindex: data.data.etnx_aindex,
            etnxp_aindex: data.data.etnxp_aindex,
            etnx_user_id: data.data.etnx_uid, 
            etnxp_user_id: data.data.etnxp_uid, 
            transactions: []
          });
        }
      })
      .catch(err => console.error(err));
  };

  return (
    <LinearGradient colors={['#FFD700', '#808080', '#000']} style={styles.container}>
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
      <Modal
        visible={showPin}
        transparent
        animationType="fade"
        onRequestClose={() => setShowPin(false)}
      >
        <Pressable style={styles.modalContainer} onPress={() => setShowPin(false)}>
          <Pressable style={styles.modalContent} onPress={() => {}}>
            <TouchableOpacity style={styles.closeBtn} onPress={() => setShowPin(false)}>
              <Text style={styles.closeText}>X</Text>
            </TouchableOpacity>
            <Text style={styles.pinLabel}>Enter 5-digit PIN</Text>
            <Text style={styles.pinDisplay}>{'\u25CF'.repeat(pin.length)}</Text>
            {[[1,2,3],[4,5,6],[7,8,9],[null,0,null]].map((row, rIdx) => (
              <View key={rIdx} style={styles.keypadRow}>
                {row.map((num, cIdx) => (
                  <TouchableOpacity
                    key={cIdx}
                    style={styles.key}
                    disabled={num === null || pin.length >= 5}
                    onPress={() => setPin(p => p + String(num))}
                  >
                    <Text style={styles.keyText}>{num !== null ? num : ''}</Text>
                  </TouchableOpacity>
                ))}
              </View>
            ))}
            <Button title="Submit" onPress={() => { setShowPin(false); submitPin(); }} />
          </Pressable>
        </Pressable>
      </Modal>
    </LinearGradient>
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
    width: '80%',
    alignItems: 'center'
  },
  closeBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    zIndex: 1
  },
  closeText: {
    fontSize: 18,
    fontWeight: 'bold'
  },
  pinLabel: {
    marginTop: 16,
    marginBottom: 8,
    fontWeight: 'bold'
  },
  pinDisplay: {
    fontSize: 24,
    marginBottom: 16
  },
  keypadRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    marginBottom: 12
  },
  key: {
    width: 50,
    height: 50,
    borderRadius: 25,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#eee'
  },
  keyText: {
    fontSize: 18
  }
});
