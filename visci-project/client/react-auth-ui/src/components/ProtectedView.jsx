import React from 'react';
import { useEffect, useState } from 'react';
import { Redirect } from 'react-router-dom';
import { getProtectedData } from '../services/api';

const ProtectedView = () => {
    const [isAuthenticated, setIsAuthenticated] = useState(null);
    const [message, setMessage] = useState('');

    useEffect(() => {
        const checkAuthentication = async () => {
            try {
                const accessToken = localStorage.getItem('accessToken');
                if (!accessToken) {
                    throw new Error('No access token found');
                }

                const response = await getProtectedData(accessToken);
                setMessage(response.data.message);
                setIsAuthenticated(true);
            } catch (error) {
                setIsAuthenticated(false);
            }
        };

        checkAuthentication();
    }, []);

    if (isAuthenticated === null) {
        return <div>Loading...</div>;
    }

    if (!isAuthenticated) {
        return <Redirect to="/login" />;
    }

    return (
        <div>
            <h1>Protected Content</h1>
            <p>{message}</p>
        </div>
    );
};

export default ProtectedView;