import axios from 'axios';

const API_URL = 'http://localhost:8000/api'; // Update with your Django API URL

export const login = async (username, password) => {
    try {
        const response = await axios.post(`${API_URL}/login/`, { username, password });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : { error: 'An error occurred during login' };
    }
};

export const register = async (username, password) => {
    try {
        const response = await axios.post(`${API_URL}/register/`, { username, password });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : { error: 'An error occurred during registration' };
    }
};

export const getProtectedData = async (accessToken) => {
    try {
        const response = await axios.get(`${API_URL}/protected/`, {
            headers: {
                Authorization: `Bearer ${accessToken}`,
            },
        });
        return response.data;
    } catch (error) {
        throw error.response ? error.response.data : { error: 'An error occurred while accessing protected data' };
    }
};