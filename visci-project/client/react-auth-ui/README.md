# React Authentication UI

This project is a React-based front-end user interface for testing authentication views in a Django API. It provides forms for user login and registration, as well as a protected view that can only be accessed by authenticated users.

## Project Structure

```
react-auth-ui
├── public
│   ├── index.html         # Main HTML file for the React application
│   └── favicon.ico        # Favicon for the application
├── src
│   ├── components         # Contains React components
│   │   ├── LoginForm.jsx  # Component for user login
│   │   ├── RegisterForm.jsx # Component for user registration
│   │   └── ProtectedView.jsx # Component for protected content
│   ├── services           # Contains API service functions
│   │   └── api.js        # API calls to the Django backend
│   ├── App.jsx            # Main application component
│   ├── index.js           # Entry point of the React application
│   └── styles             # Contains CSS styles
│       └── App.css       # Styles for the application
├── package.json           # Configuration file for npm
├── .gitignore             # Specifies files to ignore by Git
└── README.md              # Documentation for the project
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd react-auth-ui
   ```

2. **Install dependencies:**
   ```
   npm install
   ```

3. **Run the application:**
   ```
   npm start
   ```

4. **Access the application:**
   Open your browser and navigate to `http://localhost:3000`.

## Usage

- Use the **LoginForm** component to log in with your credentials.
- Use the **RegisterForm** component to create a new user account.
- Access the **ProtectedView** component to see content that requires authentication.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.