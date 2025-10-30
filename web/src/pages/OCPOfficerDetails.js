import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import apiClient from '../components/utils/axios';
import useAuthToken from '../hooks/userAuth';
import OrganizationNavbar from '../components/shared/OrganizationNavbar';
import StarBorder from '../components/ui/StarBorder';

const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    return new Date(dateString).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch {
    return dateString;
  }
};

const getEventTypeColor = (eventType) => {
  switch (eventType) {
    case 'GBM': return 'bg-soda-blue/20 text-soda-blue';
    case 'Special Event': return 'bg-soda-red/20 text-soda-red';
    case 'Workshop': return 'bg-green-500/20 text-green-400';
    case 'Social': return 'bg-yellow-500/20 text-yellow-400';
    case 'Special Contribution': return 'bg-purple-500/20 text-purple-400';
    default: return 'bg-soda-gray text-soda-white/70';
  }
};

const formatDecimal = (value, digits = 2) => {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric)) return '0.00';
  return numeric.toFixed(digits);
};

const OCPOfficerDetails = () => {
  useAuthToken();
  const { orgPrefix, officerUuid } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [startDate, setStartDate] = useState(searchParams.get('start_date') || '');
  const [endDate, setEndDate] = useState(searchParams.get('end_date') || '');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [officerData, setOfficerData] = useState(null);
  const [weightDrafts, setWeightDrafts] = useState({});
  const [weightSaving, setWeightSaving] = useState({});
  const [notification, setNotification] = useState({ open: false, message: '', type: 'info' });

  const fetchOfficerData = useCallback(async () => {
    if (!officerUuid) return;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.append('officer_uuid', officerUuid);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);

    try {
      const response = await apiClient.get(`/api/ocp/officer-points?${params.toString()}`);
      const payload = response.data;
      const officerEntries = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.officer_points)
          ? payload.officer_points
          : [];

      const record = officerEntries.find(entry => entry.officer_uuid === officerUuid) || officerEntries[0] || null;
      setOfficerData(record);
      setWeightDrafts({});
      setWeightSaving({});
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Unable to load officer details.');
    } finally {
      setLoading(false);
    }
  }, [officerUuid, startDate, endDate]);

  useEffect(() => {
    fetchOfficerData();
  }, [fetchOfficerData]);

  const handleWeightDraftChange = useCallback((pointId, value) => {
    setWeightDrafts(prev => ({ ...prev, [pointId]: value }));
  }, []);

  const handleWeightSave = useCallback(async (contribution) => {
    const rawDraft = weightDrafts[contribution.id];
    const fallback = contribution.weight != null ? formatDecimal(contribution.weight, 2) : '1.00';
    const targetValue = rawDraft !== undefined ? rawDraft : fallback;
    const parsed = parseFloat(targetValue);

    if (Number.isNaN(parsed) || parsed < 0) {
      setNotification({
        open: true,
        message: 'Weight must be a non-negative number with up to two decimal places.',
        type: 'error',
      });
      return;
    }

    const normalized = Math.round(parsed * 100) / 100;
    const currentWeight = contribution.weight != null ? Math.round(Number(contribution.weight) * 100) / 100 : 1;

    if (normalized === currentWeight) {
      return;
    }

    setWeightSaving(prev => ({ ...prev, [contribution.id]: true }));

    try {
      const response = await apiClient.put(`/api/ocp/contribution/${contribution.id}`, { weight: normalized });
      if (response?.data?.status === 'error') {
        throw new Error(response.data.message || 'Failed to update weight.');
      }

      setNotification({
        open: true,
        message: 'Weight updated successfully.',
        type: 'success',
      });

      setWeightDrafts(prev => {
        const next = { ...prev };
        delete next[contribution.id];
        return next;
      });

      await fetchOfficerData();
    } catch (err) {
      setNotification({
        open: true,
        message: err.response?.data?.message || err.message || 'Failed to update weight.',
        type: 'error',
      });
    } finally {
      setWeightSaving(prev => {
        const next = { ...prev };
        delete next[contribution.id];
        return next;
      });
    }
  }, [weightDrafts, fetchOfficerData]);

  const handleClearFilters = useCallback(() => {
    setStartDate('');
    setEndDate('');
  }, []);

  const handleBack = useCallback(() => {
    if (orgPrefix) {
      navigate(`/${orgPrefix}/ocp`);
    } else {
      navigate(-1);
    }
  }, [navigate, orgPrefix]);

  return (
    <OrganizationNavbar>
      <div className="max-w-6xl mx-auto p-4 md:p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <button
              onClick={handleBack}
              className="text-soda-blue hover:text-soda-red transition-colors text-sm border border-soda-blue hover:border-soda-red px-3 py-1.5 rounded-md"
            >
              Back to Officers
            </button>
            <h1 className="text-3xl sm:text-4xl font-bold text-soda-white tracking-tight mt-4">
              Officer Contribution Details
            </h1>
            {officerData && (
              <p className="text-soda-white/70 mt-2">
                {officerData.officer_name} • {officerData.officer_title || 'Unknown Role'} • {officerData.officer_department || 'Unknown Department'}
              </p>
            )}
          </div>
        </div>

        <div className="bg-soda-gray/70 backdrop-blur-md p-4 md:p-6 rounded-xl mb-6 border border-soda-white/10">
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 min-w-[180px]">
              <label htmlFor="start-date" className="block text-sm font-medium text-soda-white/90 mb-2">Start Date</label>
              <input
                type="month"
                id="start-date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 [color-scheme:dark]"
              />
            </div>
            <div className="flex-1 min-w-[180px]">
              <label htmlFor="end-date" className="block text-sm font-medium text-soda-white/90 mb-2">End Date</label>
              <input
                type="month"
                id="end-date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full p-3 rounded-lg bg-soda-black/60 border border-soda-white/30 [color-scheme:dark]"
              />
            </div>
            <div className="flex gap-3 w-full sm:w-auto">
              <StarBorder as="button" color="#007AFF" onClick={fetchOfficerData} className="py-2.5 text-sm flex-1">
                Apply
              </StarBorder>
              <StarBorder as="button" color="#FF3B30" onClick={handleClearFilters} className="py-2.5 text-sm flex-1">
                Clear
              </StarBorder>
            </div>
          </div>
        </div>

        {loading ? (
          <p className="text-center text-soda-white/70 py-10">Loading officer contributions...</p>
        ) : error ? (
          <p className="text-center text-red-400 py-10">{error}</p>
        ) : !officerData ? (
          <p className="text-center text-soda-white/70 py-10">No contribution data available for this officer.</p>
        ) : (
          <div className="space-y-6">
            <div className="bg-soda-gray/70 backdrop-blur-xl rounded-xl border border-soda-white/10 p-6">
              <h2 className="text-xl font-semibold text-soda-white mb-4">Points Summary</h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-soda-black/30 rounded-lg p-4 border border-soda-white/10">
                  <p className="text-sm text-soda-white/60">Total Weighted Points</p>
                  <p className="text-2xl font-bold text-soda-blue mt-1">{formatDecimal(officerData.total_points, 2)}</p>
                </div>
                <div className="bg-soda-black/30 rounded-lg p-4 border border-soda-white/10">
                  <p className="text-sm text-soda-white/60">Total Base Points</p>
                  <p className="text-2xl font-bold text-soda-white mt-1">{formatDecimal(officerData.total_base_points, 2)}</p>
                </div>
              </div>
            </div>

            <div className="bg-soda-gray/70 backdrop-blur-xl rounded-xl overflow-hidden border border-soda-white/10">
              <div className="overflow-x-auto">
                <table className="min-w-full table-auto text-left text-soda-white/90">
                  <thead className="bg-soda-black/30 text-soda-white/70 uppercase text-xs">
                    <tr>
                      {['Event', 'Type', 'Role', 'Base Points', 'Weight', 'Weighted Points', 'Event Date', 'Actions'].map(header => (
                        <th key={header} className="px-4 py-3">{header}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-soda-white/10">
                    {officerData.contributions && officerData.contributions.length > 0 ? officerData.contributions.map(contribution => {
                      const draftValue = weightDrafts[contribution.id];
                      const inputValue = draftValue !== undefined ? draftValue : formatDecimal(contribution.weight ?? 1, 2);
                      const isSaving = !!weightSaving[contribution.id];
                      const normalizedCurrent = Math.round(((contribution.weight != null ? Number(contribution.weight) : 1) * 100)) / 100;
                      const draftNumber = parseFloat(inputValue);
                      const isValidDraft = !Number.isNaN(draftNumber) && draftNumber >= 0;
                      const normalizedDraft = isValidDraft ? Math.round(draftNumber * 100) / 100 : normalizedCurrent;
                      const hasChanges = draftValue !== undefined && isValidDraft && normalizedDraft !== normalizedCurrent;
                      const weightedDisplay = formatDecimal(contribution.weighted_points ?? contribution.points * (contribution.weight ?? 1), 2);

                      return (
                        <tr key={contribution.id} className="hover:bg-soda-black/20">
                          <td className="px-4 py-3 whitespace-nowrap">{contribution.event}</td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`px-2 py-0.5 rounded-full ${getEventTypeColor(contribution.event_type)}`}>
                              {contribution.event_type || 'Other'}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">{contribution.role || 'N/A'}</td>
                          <td className="px-4 py-3 whitespace-nowrap">{formatDecimal(contribution.points, 2)}</td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <input
                              type="number"
                              step="0.01"
                              min="0"
                              value={inputValue}
                              onChange={(e) => handleWeightDraftChange(contribution.id, e.target.value)}
                              className="w-24 p-2 rounded-md bg-soda-black/50 border border-soda-white/20 text-right"
                              disabled={isSaving}
                            />
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-semibold">{weightedDisplay}</td>
                          <td className="px-4 py-3 whitespace-nowrap">{formatDate(contribution.timestamp)}</td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <button
                              onClick={() => handleWeightSave(contribution)}
                              disabled={isSaving || !hasChanges}
                              className={`px-3 py-1 rounded-md text-xs ${
                                isSaving || !hasChanges
                                  ? 'bg-soda-gray/40 text-soda-white/40 cursor-not-allowed'
                                  : 'bg-soda-blue text-white hover:bg-soda-blue/80'
                              }`}
                            >
                              {isSaving ? 'Saving...' : 'Save'}
                            </button>
                          </td>
                        </tr>
                      );
                    }) : (
                      <tr>
                        <td colSpan={8} className="px-4 py-6 text-center text-soda-white/60">
                          No contributions found for the selected period.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {notification.open && (
          <div className={`fixed bottom-5 right-5 p-4 rounded-lg shadow-xl text-soda-white max-w-sm z-50 backdrop-blur-md
            ${notification.type === 'success' ? 'bg-green-600/90' : notification.type === 'error' ? 'bg-red-700/90' : 'bg-soda-gray/90'}`}>
            <div className="flex justify-between items-center">
              <p>{notification.message}</p>
              <button onClick={() => setNotification({ ...notification, open: false })} className="ml-4 text-xl">&times;</button>
            </div>
          </div>
        )}
      </div>
    </OrganizationNavbar>
  );
};

export default OCPOfficerDetails;
