import axios from 'axios';
import config from '../../config';


export const getName = async() => {
  try {
    const response = await axios.get(`${config.apiUrl}/auth/name`,{
      headers: {
        'Authorization': `${localStorage.getItem('token')}`
      }
  });
    return response.data;
  } catch (error) {
    console.error("Error fetching name", error);
    throw error;
  }
}

export const getLeaderboard = async () => {
  try {
    const response = await axios.get(`${config.apiUrl}/points/leaderboard`);
    return response.data;
  } catch (error) {
    console.error("Error fetching leaderboard", error);
    throw error;
  }
};

export const addPoints = async (userId, eventName, points) => {
  try {
    const response = await axios.post(`${config.apiUrl}/add-points`, {
      user_id: userId,
      event: eventName,
      points: points
    });
    return response.data;
  } catch (error) {
    console.error("Error adding points", error);
    throw error;
  }
};

export const removePoints = async (userId, points) => {
  try {
    const response = await axios.post(`${config.apiUrl}/remove-points`, {
      user_id: userId,
      points: points
    });
    return response.data;
  } catch (error) {
    console.error("Error removing points", error);
    throw error;
  }
};
