import React from 'react';
import { BrowserRouter as Router, Route, Switch } from 'react-router-dom';
import LoginForm from './components/LoginForm';
import RegisterForm from './components/RegisterForm';
import ProtectedView from './components/ProtectedView';
import './styles/App.css';

function App() {
    return (
        <Router>
            <div className="App">
                <Switch>
                    <Route path="/login" component={LoginForm} />
                    <Route path="/register" component={RegisterForm} />
                    <Route path="/protected" component={ProtectedView} />
                    <Route path="/" exact>
                        <h1>Welcome to the Authentication App</h1>
                    </Route>
                </Switch>
            </div>
        </Router>
    );
}

export default App;