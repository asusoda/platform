import React, { useState, useEffect } from 'react';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import useOrgNavigation from '../hooks/useOrgNavigation';
import { useAuth } from '../components/auth/AuthContext';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';
import { FaUsers, FaSignOutAlt, FaTachometerAlt, FaClipboardList, FaTrashAlt, FaTimes, FaCogs, FaEdit, FaSave } from 'react-icons/fa';

const LeaderboardPage = () => {
  useAuthToken();
  const { currentOrg } = useAuth();
  const { 
    goToDashboard,
    goToUsers, 
    goToAddPoints,
    goToOCP,
    goToPanel,
    goToJeopardy 
  } = useOrgNavigation();

  const [leaderboardData, setLeaderboardData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [showModal, setShowModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [selectedUserEmail, setSelectedUserEmail] = useState('');
  const [loadingUser, setLoadingUser] = useState(false);
  const [modalError, setModalError] = useState('');
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [pointToDelete, setPointToDelete] = useState(null);

  // Enhanced admin features
  const [isEditing, setIsEditing] = useState(false);
  const [editFormData, setEditFormData] = useState({});
  const [saveLoading, setSaveLoading] = useState(false);

  const handleDeleteClick = (event) => {
    setPointToDelete(event);
    setShowConfirmModal(true);
  };

  const handleConfirmedDelete = async () => {
    if (pointToDelete && selectedUserEmail) {
      setDeleteLoading(true);
      try {
        await apiClient.request({
          method: 'DELETE',
          url: `/api/points/${currentOrg.prefix}/delete_points`,
          data: {
            user_email: selectedUserEmail,
            event: pointToDelete.event
          }
        });
        await viewUserDetails(selectedUserEmail);
        setShowConfirmModal(false);
        setPointToDelete(null);
      } catch (error) {
        setModalError(error.response?.data?.error || 'Error deleting points');
      } finally {
        setDeleteLoading(false);
      }
    }
  };

  const viewUserDetails = async (userEmail) => {
    setLoadingUser(true);
    setModalError('');
    setIsEditing(false); // Reset editing state
    try {
      // Use the new consolidated endpoint to get user details with points history
      const response = await apiClient.get(`/api/points/${currentOrg.prefix}/users/${encodeURIComponent(userEmail)}/points`);
      const userData = {
        ...response.data.user,
        points_history: response.data.points_history || [],
        total_points: response.data.total_points || 0
      };
      setSelectedUser(userData);
      setEditFormData({
        name: userData.name || '',
        username: userData.username || '',
        asu_id: userData.asu_id || '',
        academic_standing: userData.academic_standing || '',
        major: userData.major || ''
      });
      setSelectedUserEmail(userEmail);
      setShowModal(true);
    } catch (error) {
      setModalError(error.response?.data?.error || 'Failed to fetch user details');
    } finally {
      setLoadingUser(false);
    }
  };

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    setModalError('');
  };

  const handleEditFormChange = (field, value) => {
    setEditFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSaveUser = async () => {
    setSaveLoading(true);
    setModalError('');
    
    try {
      const response = await apiClient.put(
        `/api/points/${currentOrg.prefix}/users/${encodeURIComponent(selectedUserEmail)}`,
        editFormData
      );
      
      // Update the selected user data
      setSelectedUser(prev => ({
        ...prev,
        ...editFormData
      }));
      
      setIsEditing(false);
      // Refresh leaderboard to show updated information
      fetchLeaderboard();
    } catch (error) {
      setModalError(error.response?.data?.error || 'Failed to update user information');
    } finally {
      setSaveLoading(false);
    }
  };

  const fetchLeaderboard = async () => {
    try {
      setLoading(true);
      if (!currentOrg?.prefix) {
        setError('No organization selected');
        return;
      }
      
      const response = await apiClient.get(`/api/public/${currentOrg.prefix}/leaderboard`);
      setLeaderboardData(response.data.leaderboard || []);
    } catch (error) {
      setError('Failed to fetch leaderboard data');
      console.error('Error fetching leaderboard:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeaderboard();
  }, [currentOrg]);

  return (
    <OrganizationNavbar>
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold mb-2">Leaderboard</h1>
          <p className="text-gray-400">View points rankings and user statistics</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-400">Loading leaderboard...</p>
            </div>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-red-400">{error}</p>
          </div>
        ) : (
          <div className="bg-gray-900/50 backdrop-blur-sm rounded-xl border border-gray-700 p-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Rank</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">User</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Email</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Points</th>
                    <th className="py-3 px-4 text-sm font-semibold text-gray-300">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {leaderboardData.map((user, index) => (
                    <tr key={user.email} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                      <td className="py-4 px-4">
                        <div className="flex items-center">
                          <span className={`text-lg font-bold ${
                            index === 0 ? 'text-yellow-400' : 
                            index === 1 ? 'text-gray-300' : 
                            index === 2 ? 'text-amber-600' : 'text-gray-400'
                          }`}>
                            #{index + 1}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4">
                        <div className="flex items-center">
                          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                            {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
                          </div>
                          <div className="ml-3">
                            <div className="text-white font-medium">{user.name || 'Unknown User'}</div>
                            <div className="text-sm text-gray-400">{user.asu_id || 'No ASU ID'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-4 text-gray-300">{user.email}</td>
                      <td className="py-4 px-4">
                        <span className="text-lg font-bold text-green-400">{user.total_points || 0}</span>
                      </td>
                      <td className="py-4 px-4">
                        <button
                          onClick={() => viewUserDetails(user.email)}
                          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition-colors"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* User Details Modal */}
        {showModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-900 rounded-xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-white">User Details</h2>
                <div className="flex items-center space-x-2">
                  {!isEditing ? (
                    <button
                      onClick={handleEditToggle}
                      className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-md transition-colors flex items-center"
                      title="Edit user information"
                    >
                      <FaEdit className="mr-1" size={12} />
                      Edit
                    </button>
                  ) : (
                    <div className="flex space-x-2">
                      <button
                        onClick={handleSaveUser}
                        disabled={saveLoading}
                        className="px-3 py-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white text-sm rounded-md transition-colors flex items-center"
                        title="Save changes"
                      >
                        <FaSave className="mr-1" size={12} />
                        {saveLoading ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={handleEditToggle}
                        className="px-3 py-1 bg-gray-600 hover:bg-gray-700 text-white text-sm rounded-md transition-colors"
                        title="Cancel editing"
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                  <button
                    onClick={() => setShowModal(false)}
                    className="text-gray-400 hover:text-white"
                  >
                    <FaTimes size={24} />
                  </button>
                </div>
              </div>

              {loadingUser ? (
                <div className="text-center py-8">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
                  <p className="text-gray-400">Loading user details...</p>
                </div>
              ) : modalError ? (
                <div className="text-red-400 text-center py-4">{modalError}</div>
              ) : selectedUser ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Name</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editFormData.name}
                          onChange={(e) => handleEditFormChange('name', e.target.value)}
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                        />
                      ) : (
                        <p className="text-white">{selectedUser.name || 'N/A'}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Username</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editFormData.username}
                          onChange={(e) => handleEditFormChange('username', e.target.value)}
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                          placeholder="Optional username"
                        />
                      ) : (
                        <p className="text-white">{selectedUser.username || 'N/A'}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Email</label>
                      <p className="text-white">{selectedUser.email}</p>
                      <p className="text-xs text-gray-500">Email cannot be changed</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">ASU ID</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editFormData.asu_id}
                          onChange={(e) => handleEditFormChange('asu_id', e.target.value)}
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                          placeholder="10-digit ASU ID"
                        />
                      ) : (
                        <p className="text-white">{selectedUser.asu_id || 'N/A'}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Academic Standing</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editFormData.academic_standing}
                          onChange={(e) => handleEditFormChange('academic_standing', e.target.value)}
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                          placeholder="e.g., Sophomore"
                        />
                      ) : (
                        <p className="text-white">{selectedUser.academic_standing || 'N/A'}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1">Major</label>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editFormData.major}
                          onChange={(e) => handleEditFormChange('major', e.target.value)}
                          className="w-full px-3 py-2 bg-gray-800 border border-gray-600 rounded-md text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
                          placeholder="e.g., Computer Science"
                        />
                      ) : (
                        <p className="text-white">{selectedUser.major || 'N/A'}</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-300 mb-2">Points History</label>
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      {selectedUser.points_history && selectedUser.points_history.length > 0 ? (
                        selectedUser.points_history.map((point, index) => (
                          <div key={point.id || index} className="flex items-center justify-between p-3 bg-gray-800 rounded-lg">
                            <div className="flex-1">
                              <div className="text-white font-medium">{point.event || 'No event specified'}</div>
                              <div className="text-sm text-gray-400">
                                {point.timestamp ? new Date(point.timestamp).toLocaleDateString() : 'Unknown date'}
                                {point.awarded_by_officer && (
                                  <span className="ml-2">• Awarded by: {point.awarded_by_officer}</span>
                                )}
                              </div>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="text-green-400 font-bold">+{point.points}</span>
                              <button
                                onClick={() => handleDeleteClick(point)}
                                className="text-red-400 hover:text-red-300"
                                title="Delete this point entry"
                              >
                                <FaTrashAlt size={16} />
                              </button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-400 text-center py-4">No points history available</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}

        {/* Confirmation Modal */}
        {showConfirmModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full mx-4">
              <h3 className="text-lg font-bold text-white mb-4">Confirm Deletion</h3>
              <p className="text-gray-300 mb-6">
                Are you sure you want to delete the points for "{pointToDelete?.event}"?
                This action cannot be undone.
              </p>
              <div className="flex space-x-3">
                <button
                  onClick={() => setShowConfirmModal(false)}
                  className="flex-1 px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmedDelete}
                  disabled={deleteLoading}
                  className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-md transition-colors"
                >
                  {deleteLoading ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default LeaderboardPage;