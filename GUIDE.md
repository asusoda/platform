# ASU SODA Platform Setup Guide

## Overview

This guide provides comprehensive instructions for setting up and using the ASU SODA platform for organizational onboarding. The platform streamlines member management, project coordination, and administrative tasks for student organizations.

## Prerequisites

- Node.js 18+ installed
- Git configured with your credentials
- Access to ASU SODA organization repository
- Basic familiarity with command line interface

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/asusoda/platform.git
cd platform
```

### 2. Install Dependencies

```bash
npm install
# or
yarn install
```

### 3. Environment Configuration

Copy the example environment file and configure your local settings:

```bash
cp .env.example .env
```

Update the `.env` file with your specific configuration:

```env
DATABASE_URL="your_database_connection_string"
API_KEY="your_api_key"
NEXT_PUBLIC_BASE_URL="http://localhost:3000"
```

### 4. Database Setup

Run database migrations:

```bash
npm run db:migrate
# Seed initial data (optional)
npm run db:seed
```

### 5. Start Development Server

```bash
npm run dev
```

The application will be available at `http://localhost:3000`

## Core Features

### Member Management

- **Registration**: New members can register through the platform
- **Profile Management**: Users can update their information and preferences
- **Role Assignment**: Administrators can assign roles and permissions
- **Directory**: Browse and search organization members

### Project Coordination

- **Project Creation**: Create new projects with descriptions and timelines
- **Task Assignment**: Assign tasks to team members
- **Progress Tracking**: Monitor project milestones and completion status
- **Collaboration Tools**: Built-in messaging and file sharing

### Administrative Dashboard

- **Analytics**: View organization metrics and member engagement
- **Event Management**: Schedule and manage organization events
- **Communication**: Send announcements and newsletters
- **Reports**: Generate membership and activity reports

## API Usage

### Authentication

The platform uses JWT tokens for authentication. Include the token in your request headers:

```javascript
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};
```

### Common Endpoints

#### Get Members

```javascript
GET /api/members
```

Response:
```json
{
  "members": [
    {
      "id": "123",
      "name": "John Doe",
      "email": "john@asu.edu",
      "role": "member",
      "joinDate": "2024-01-15"
    }
  ]
}
```

#### Create Project

```javascript
POST /api/projects

Body:
{
  "title": "New Project",
  "description": "Project description",
  "dueDate": "2024-12-31",
  "assignedMembers": ["123", "456"]
}
```

#### Update Member Profile

```javascript
PUT /api/members/:id

Body:
{
  "name": "Updated Name",
  "email": "updated@asu.edu",
  "bio": "Updated bio information"
}
```

### Error Handling

The API returns standard HTTP status codes:

- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `500`: Internal Server Error

Error responses include descriptive messages:

```json
{
  "error": "Validation failed",
  "message": "Email address is required",
  "code": 400
}
```

## Deployment

### Production Build

```bash
npm run build
npm start
```

### Environment Variables for Production

Ensure these variables are set in your production environment:

- `NODE_ENV=production`
- `DATABASE_URL`: Production database connection
- `JWT_SECRET`: Strong secret for token signing
- `API_BASE_URL`: Production API base URL

### Docker Deployment

A Dockerfile is provided for containerized deployment:

```bash
docker build -t soda-platform .
docker run -p 3000:3000 soda-platform
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify your database URL in the `.env` file
   - Ensure the database server is running
   - Check network connectivity

2. **Authentication Errors**
   - Verify JWT_SECRET is set correctly
   - Check token expiration
   - Ensure proper header format

3. **Build Failures**
   - Clear node_modules and reinstall: `rm -rf node_modules package-lock.json && npm install`
   - Check Node.js version compatibility
   - Verify all environment variables are set

### Getting Help

- Check the [Issues](https://github.com/asusoda/platform/issues) page for known problems
- Create a new issue with detailed error information
- Contact the development team through Slack
- Review the [Wiki](https://github.com/asusoda/platform/wiki) for additional documentation

## Contributing

### Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and test thoroughly
4. Commit with descriptive messages
5. Push to your fork and create a pull request

### Code Style

- Follow ESLint configuration
- Use Prettier for code formatting
- Write meaningful commit messages
- Include tests for new features

### Pull Request Process

1. Ensure all tests pass
2. Update documentation as needed
3. Request review from maintainers
4. Address feedback and iterate
5. Merge after approval

## Security Considerations

- Never commit sensitive information (API keys, passwords)
- Use environment variables for configuration
- Keep dependencies updated
- Follow secure coding practices
- Report security issues privately

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Support

For technical support or questions about the platform:

- Email: soda-platform@asu.edu
- Slack: #platform-support
- Office Hours: Tuesdays 2-4 PM, Engineering Center Room 123

---

*Last updated: September 2024*
