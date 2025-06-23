import * as React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';
import Home from './screens/Home';
import TransactionDetails from './screens/TransactionDetails';
import Transfer from './screens/Transfer';

const Stack = createStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName="Home">
        <Stack.Screen name="Home" component={Home} />
        <Stack.Screen name="TransactionDetails" component={TransactionDetails} options={{ title: 'Transaction Details' }} />
        <Stack.Screen name="Transfer" component={Transfer} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
