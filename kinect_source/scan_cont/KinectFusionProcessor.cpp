//------------------------------------------------------------------------------
// <copyright file="KinectFusionProcessor.cpp" company="Microsoft">
//     Copyright (c) Microsoft Corporation.  All rights reserved.
// </copyright>
//------------------------------------------------------------------------------

// System includes
#include "stdafx.h"
#include <string>
#include <fstream>

#pragma warning(push)
#pragma warning(disable:6255)
#pragma warning(disable:6263)
#pragma warning(disable:4995)
#include "ppl.h"
#pragma warning(pop)

// Project includes
#include "KinectFusionProcessor.h"
#include "KinectFusionHelper.h"
#include "resource.h"

#define AssertOwnThread() \
    _ASSERT_EXPR(GetCurrentThreadId() == m_threadId, __FUNCTIONW__ L" called on wrong thread!");

#define AssertOtherThread() \
    _ASSERT_EXPR(GetCurrentThreadId() != m_threadId, __FUNCTIONW__ L" called on wrong thread!");

bool myEquals (Vector3 i, Vector3 j) {
    return ((i.x==j.x) && (i.y == j.y) && (i.z == j.z));
}

bool myLess (Vector3 i, Vector3 j) {
    if (i.x < j.x)
        return true;
    else if (i.x == j.x)
        if ( i.y < j.y)
            return true;
        else if (i.y == j.y)
            if (i.z < j.z)
                return true;
            else
                return false;
        else
            return false;
    else
        return false;

}

/// <summary>
/// Constructor
/// </summary>
KinectFusionProcessor::KinectFusionProcessor() :
    m_hWnd(nullptr),
    m_msgFrameReady(WM_NULL),
    m_msgUpdateSensorStatus(WM_NULL),
    m_hThread(nullptr),
    m_threadId(0),
    m_pVolume(nullptr),
    m_hrRecreateVolume(S_OK),
    m_pSensorChooser(nullptr),
    m_hStatusChangeEvent(INVALID_HANDLE_VALUE),
    m_pNuiSensor(nullptr),
    m_hNextDepthFrameEvent(INVALID_HANDLE_VALUE),
    m_pDepthStreamHandle(INVALID_HANDLE_VALUE),
    m_hNextColorFrameEvent(INVALID_HANDLE_VALUE),
    m_pColorStreamHandle(INVALID_HANDLE_VALUE),
    m_cLostFrameCounter(0),
    m_bTrackingFailed(false),
    m_cFrameCounter(0),
    m_exportFrameCounter(0),
    m_fFrameCounterStartTime(0),
    m_cLastDepthFrameTimeStamp(0),
    m_cLastColorFrameTimeStamp(0),
    m_fMostRecentRaycastTime(0),
    m_pDepthImagePixelBuffer(nullptr),
    m_pColorCoordinates(nullptr),
    m_pMapper(nullptr),
    m_cPixelBufferLength(0),
    m_cColorCoordinateBufferLength(0),
    m_pDepthFloatImage(nullptr),
    m_pColorImage(nullptr),
    m_pResampledColorImage(nullptr),
    m_pResampledColorImageDepthAligned(nullptr),
    m_pSmoothDepthFloatImage(nullptr),
    m_pDepthPointCloud(nullptr),
    m_pRaycastPointCloud(nullptr),
    m_pRaycastDepthFloatImage(nullptr),
    m_pShadedSurface(nullptr),
    m_pShadedSurfaceNormals(nullptr),
    m_pCapturedSurfaceColor(nullptr),
    m_pFloatDeltaFromReference(nullptr),
    m_pShadedDeltaFromReference(nullptr),
    m_bKinectFusionInitialized(false),
    m_bResetReconstruction(false),
    m_bResolveSensorConflict(false),
    m_bIntegrationResumed(false),
    m_hStopProcessingEvent(INVALID_HANDLE_VALUE),
    m_pCameraPoseFinder(nullptr),
    m_bTrackingHasFailedPreviously(false),
    m_pDownsampledDepthFloatImage(nullptr),
    m_pDownsampledSmoothDepthFloatImage(nullptr),
    m_pDownsampledDepthPointCloud(nullptr),
    m_pDownsampledShadedDeltaFromReference(nullptr),
    m_pDownsampledRaycastPointCloud(nullptr),
    m_bCalculateDeltaFrame(false)
{
    // Initialize synchronization objects
    InitializeCriticalSection(&m_lockParams);
    InitializeCriticalSection(&m_lockFrame);
    InitializeCriticalSection(&m_lockVolume);

    m_hStatusChangeEvent = CreateEvent(
        nullptr,
        FALSE, /* bManualReset */ 
        FALSE, /* bInitialState */
        nullptr);
    m_hNextDepthFrameEvent = CreateEvent(
        nullptr,
        TRUE, /* bManualReset */ 
        FALSE, /* bInitialState */
        nullptr);
    m_hNextColorFrameEvent = CreateEvent(
        nullptr,
        TRUE, /* bManualReset */ 
        FALSE, /* bInitialState */
        nullptr);
    m_hStopProcessingEvent = CreateEvent(
        nullptr,
        TRUE, /* bManualReset */ 
        FALSE, /* bInitialState */
        nullptr
        );

    SetIdentityMatrix(m_worldToCameraTransform);
    SetIdentityMatrix(m_defaultWorldToVolumeTransform);
}

/// <summary>
/// Destructor
/// </summary>
KinectFusionProcessor::~KinectFusionProcessor()
{
    AssertOtherThread();

    // Shutdown the sensor
    StopProcessing();

    // Clean up Kinect Fusion
    SafeRelease(m_pVolume);
    SafeRelease(m_pMapper);

    // Clean up Kinect Fusion Camera Pose Finder
    SafeRelease(m_pCameraPoseFinder);

    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDepthFloatImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pColorImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pResampledColorImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pResampledColorImageDepthAligned);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pRaycastPointCloud);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pRaycastDepthFloatImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pShadedSurface);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pShadedSurfaceNormals);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pCapturedSurfaceColor);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pFloatDeltaFromReference);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pShadedDeltaFromReference);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pSmoothDepthFloatImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDepthPointCloud);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDownsampledDepthFloatImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDownsampledSmoothDepthFloatImage);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDownsampledDepthPointCloud);
    SAFE_FUSION_RELEASE_IMAGE_FRAME(m_pDownsampledShadedDeltaFromReference);

    // Clean up the depth pixel array
    SAFE_DELETE_ARRAY(m_pDepthImagePixelBuffer);

    // Clean up the color coordinate array
    SAFE_DELETE_ARRAY(m_pColorCoordinates);

    // Clean up synchronization objects
    if (m_hNextDepthFrameEvent != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hNextDepthFrameEvent);
    }
    if (m_hNextColorFrameEvent != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hNextColorFrameEvent);
    }
    if (m_hStatusChangeEvent != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hStatusChangeEvent);
    }
    if (m_hStopProcessingEvent != INVALID_HANDLE_VALUE)
    {
        CloseHandle(m_hStopProcessingEvent);
    }

    DeleteCriticalSection(&m_lockParams);
    DeleteCriticalSection(&m_lockFrame);
    DeleteCriticalSection(&m_lockVolume);
}

/// <summary>
/// Shuts down the sensor
/// </summary>
void KinectFusionProcessor::ShutdownSensor()
{
    AssertOwnThread();

    // Clean up Kinect
    if (m_pNuiSensor != nullptr)
    {
        m_pNuiSensor->NuiShutdown();
        SafeRelease(m_pNuiSensor);
    }
}

/// <summary>
/// Starts Kinect Fusion processing.
/// </summary>
/// <param name="phThread">returns the new processing thread's handle</param>
HRESULT KinectFusionProcessor::StartProcessing()
{
    AssertOtherThread();

    if (m_hThread == nullptr)
    {
        m_hThread = CreateThread(nullptr, 0, ThreadProc, this, 0, &m_threadId);
    }

    return (m_hThread != nullptr) ? S_OK : HRESULT_FROM_WIN32(GetLastError());
}

/// <summary>
/// Stops Kinect Fusion processing.
/// </summary>
HRESULT KinectFusionProcessor::StopProcessing()
{
    AssertOtherThread();

    if (m_hThread != nullptr)
    {
        SetEvent(m_hStopProcessingEvent);

        WaitForSingleObject(m_hThread, INFINITE);
        m_hThread = nullptr;
    }

    return S_OK;
}

/// <summary>
/// Attempt to resolve a sensor conflict.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::ResolveSensorConflict()
{
    AssertOtherThread();

    EnterCriticalSection(&m_lockParams);
    m_bResolveSensorConflict = true;
    SetEvent(m_hStatusChangeEvent);
    LeaveCriticalSection(&m_lockParams);

    return S_OK;
}

/// <summary>
/// Thread procedure
/// </summary>
DWORD WINAPI KinectFusionProcessor::ThreadProc(LPVOID lpParameter)
{
    return reinterpret_cast<KinectFusionProcessor*>(lpParameter)->MainLoop();
}

/// <summary>
/// Is reconstruction volume initialized
/// </summary>
bool KinectFusionProcessor::IsVolumeInitialized()
{
    AssertOtherThread();

    return nullptr != m_pVolume;
}

/// <summary>
/// Is the camera pose finder initialized and running.
/// </summary>
bool KinectFusionProcessor::IsCameraPoseFinderAvailable()
{
    return m_paramsCurrent.m_bAutoFindCameraPoseWhenLost 
        && nullptr != m_pCameraPoseFinder 
        && m_pCameraPoseFinder->GetStoredPoseCount() > 0;
}

/// <summary>
/// Main processing function
/// </summary>
DWORD KinectFusionProcessor::MainLoop()
{
    AssertOwnThread();

    // Bring in the first set of parameters
    EnterCriticalSection(&m_lockParams);
    m_paramsCurrent = m_paramsNext;
    LeaveCriticalSection(&m_lockParams);

    // Set the sensor status callback
    NuiSetDeviceStatusCallback(StatusChangeCallback, this);

    // Init the sensor chooser to find a valid sensor
    m_pSensorChooser = new(std::nothrow) NuiSensorChooser();
    if (nullptr == m_pSensorChooser)
    {
        SetStatusMessage(L"Memory allocation failure");
        NotifyEmptyFrame();
        return 1;
    }

    // Propagate any updates to the gpu index in use
    m_paramsNext.m_deviceIndex = m_paramsCurrent.m_deviceIndex;

    // Attempt to find a sensor for the first time
    UpdateSensorAndStatus(NUISENSORCHOOSER_SENSOR_CHANGED_FLAG);

    bool bStopProcessing = false;

    // Main loop
    while (!bStopProcessing)
    {
        HANDLE handles[] = { m_hStopProcessingEvent, m_hNextDepthFrameEvent, m_hStatusChangeEvent };
        DWORD waitResult = WaitForMultipleObjects(ARRAYSIZE(handles), handles, FALSE, INFINITE);

        // Get parameters and other external signals

        EnterCriticalSection(&m_lockParams);
        bool bChangeNearMode = m_paramsCurrent.m_bNearMode != m_paramsNext.m_bNearMode;
        bool bRecreateVolume = m_paramsCurrent.VolumeChanged(m_paramsNext);
        bool bResetReconstruction = m_bResetReconstruction;
        m_bResetReconstruction = false;
        bool bResolveSensorConflict = m_bResolveSensorConflict;
        m_bResolveSensorConflict = false;

        if (m_paramsCurrent.m_bPauseIntegration != m_paramsNext.m_bPauseIntegration)
        {
            m_bIntegrationResumed = !m_paramsNext.m_bPauseIntegration;
        }

        m_paramsCurrent = m_paramsNext;
        LeaveCriticalSection(&m_lockParams);

        switch (waitResult)
        {
        case WAIT_OBJECT_0: // m_hStopProcessingEvent
            bStopProcessing = true;
            break;

        case WAIT_OBJECT_0 + 1: // m_hNextDepthFrameEvent
            {
                if (m_bKinectFusionInitialized)
                {
                    // Clear status message from previous frame
                    SetStatusMessage(L"");

                    if (bChangeNearMode)
                    {
                        if (nullptr != m_pNuiSensor)
                        {
                            DWORD flags =
                                m_paramsCurrent.m_bNearMode ?
                                NUI_IMAGE_STREAM_FLAG_ENABLE_NEAR_MODE :
                                0;

                            m_pNuiSensor->NuiImageStreamSetImageFrameFlags(
                                m_pDepthStreamHandle,
                                flags);
                        }
                    }

                    EnterCriticalSection(&m_lockVolume);

                    if (nullptr == m_pVolume && !FAILED(m_hrRecreateVolume))
                    {
                        m_hrRecreateVolume = RecreateVolume();

                        // Set an introductory message on success
                        if (SUCCEEDED(m_hrRecreateVolume))
                        {
                            SetStatusMessage(
                                L"Click ‘Near Mode’ to change sensor range, and ‘Reset Reconstruction’ to clear!");
                        }
                    }
                    else if (bRecreateVolume)
                    {
                        m_hrRecreateVolume = RecreateVolume();
                    }
                    else if (bResetReconstruction)
                    {
                        HRESULT hr = InternalResetReconstruction();

                        if (SUCCEEDED(hr))
                        {
                            SetStatusMessage(L"Reconstruction has been reset.");
                        }
                        else
                        {
                            SetStatusMessage(L"Failed to reset reconstruction.");
                        }
                    }

                    ProcessDepth();

                    LeaveCriticalSection(&m_lockVolume);

                    NotifyFrameReady();
                }
                break;
            }

        case WAIT_OBJECT_0 + 2:  // m_hStatusChangeEvent
            {
                DWORD dwChangeFlags = 0;
                HRESULT hr = E_FAIL;

                if (nullptr != m_pSensorChooser && !bResolveSensorConflict)
                {
                    // Handle sensor status change event
                    hr = m_pSensorChooser->HandleNuiStatusChanged(&dwChangeFlags);
                }
                else if (m_pNuiSensor == nullptr && bResolveSensorConflict)
                {
                    hr = m_pSensorChooser->TryResolveConflict(&dwChangeFlags);
                }

                if (SUCCEEDED(hr))
                {
                    UpdateSensorAndStatus(dwChangeFlags);
                }
            }

            break;

        default:
            bStopProcessing = true;
        }

        if (m_pNuiSensor == nullptr)
        {
            // We have no sensor: Set frame rate to zero and notify the UI
            NotifyEmptyFrame();
        }
    }

    ShutdownSensor();

    return 0;
}

/// <summary>
/// Update the sensor and status based on the changed flags
/// </summary>
void KinectFusionProcessor::UpdateSensorAndStatus(DWORD dwChangeFlags)
{
    DWORD dwSensorStatus = NuiSensorChooserStatusNone;

    switch (dwChangeFlags)
    {
        case NUISENSORCHOOSER_SENSOR_CHANGED_FLAG:
        {
            // Free the previous sensor and try to get a new one
            SafeRelease(m_pNuiSensor);
            if (SUCCEEDED(CreateFirstConnected()))
            {
                if (SUCCEEDED(InitializeKinectFusion()))
                {
                    m_bKinectFusionInitialized = true;
                }
                else
                {
                    NotifyEmptyFrame();
                }
            }
        }
        __fallthrough;

    case NUISENSORCHOOSER_STATUS_CHANGED_FLAG:
        if (SUCCEEDED(m_pSensorChooser->GetStatus(&dwSensorStatus)))
        {
            if (m_hWnd != nullptr && m_msgUpdateSensorStatus != WM_NULL)
            {
                PostMessage(m_hWnd, m_msgUpdateSensorStatus, dwSensorStatus, 0);
            }
        }
        break;
    }
}

/// <summary>
/// This function will be called when Kinect device status changed
/// </summary>
void CALLBACK KinectFusionProcessor::StatusChangeCallback(
    HRESULT hrStatus,
    const OLECHAR* instancename,
    const OLECHAR* uniqueDeviceName,
    void* pUserData)
{
    KinectFusionProcessor* pThis = reinterpret_cast<KinectFusionProcessor*>(pUserData);
    SetEvent(pThis->m_hStatusChangeEvent);
}

/// <summary>
/// Create the first connected Kinect found 
/// </summary>
/// <returns>indicates success or failure</returns>
HRESULT KinectFusionProcessor::CreateFirstConnected()
{
    AssertOwnThread();

    // Get the Kinect and specify that we'll be using depth
    HRESULT hr = m_pSensorChooser->GetSensor(NUI_INITIALIZE_FLAG_USES_DEPTH | NUI_INITIALIZE_FLAG_USES_COLOR, &m_pNuiSensor);

    EnableWindow(GetDlgItem(m_hWnd, IDC_CHECK_NEARMODE), TRUE);

    if (SUCCEEDED(hr) && nullptr != m_pNuiSensor)
    {
        // Open a depth image stream to receive depth frames
        hr = m_pNuiSensor->NuiImageStreamOpen(
            NUI_IMAGE_TYPE_DEPTH,
            m_paramsCurrent.m_depthImageResolution,
            0,
            2,
            m_hNextDepthFrameEvent,
            &m_pDepthStreamHandle);

        if (SUCCEEDED(hr))
        {
            // Open a color image stream to receive color frames
            hr = m_pNuiSensor->NuiImageStreamOpen(
                NUI_IMAGE_TYPE_COLOR,
                m_paramsCurrent.m_colorImageResolution,
                0,
                2,
                m_hNextColorFrameEvent,
                &m_pColorStreamHandle);
        }

        if (SUCCEEDED(hr))
        {
            // Create the coordinate mapper for converting color to depth space
            hr = m_pNuiSensor->NuiGetCoordinateMapper(&m_pMapper);
        }

        if (SUCCEEDED(hr) && m_paramsCurrent.m_bNearMode)
        {
            HRESULT hr = m_pNuiSensor->NuiImageStreamSetImageFrameFlags(
                m_pDepthStreamHandle,
                NUI_IMAGE_STREAM_FLAG_ENABLE_NEAR_MODE);
            if (FAILED(hr))
            {
                CheckDlgButton(m_hWnd, IDC_CHECK_NEARMODE, BST_UNCHECKED);
                EnableWindow(GetDlgItem(m_hWnd, IDC_CHECK_NEARMODE), FALSE);
            }
            else
            {
                CheckDlgButton(m_hWnd, IDC_CHECK_NEARMODE, BST_CHECKED);
            }
        }
    }
    else
    {
        // Reset the event to non-signaled state
        ResetEvent(m_hNextDepthFrameEvent);
        ResetEvent(m_hNextColorFrameEvent);
    }

    if (nullptr == m_pNuiSensor || FAILED(hr))
    {
        SafeRelease(m_pNuiSensor);
        SetStatusMessage(L"No ready Kinect found!");
        return E_FAIL;
    }

    return hr;
}

///////////////////////////////////////////////////////////////////////////////////////////

/// <summary>
/// Sets the UI window handle.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::SetWindow(HWND hWnd, UINT msgFrameReady, UINT msgUpdateSensorStatus)
{
    AssertOtherThread();

    m_hWnd = hWnd;
    m_msgFrameReady = msgFrameReady;
    m_msgUpdateSensorStatus = msgUpdateSensorStatus;
    return S_OK;
}

/// <summary>
/// Sets the parameters.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::SetParams(const KinectFusionParams& params)
{
    AssertOtherThread();

    EnterCriticalSection(&m_lockParams);
    m_paramsNext = params;
    LeaveCriticalSection(&m_lockParams);
    return S_OK;
}

/// <summary>
/// Lock the current frame while rendering it to the screen.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::LockFrame(KinectFusionProcessorFrame const** ppFrame)
{
    AssertOtherThread();

    EnterCriticalSection(&m_lockFrame);
    *ppFrame = &m_frame;

    return S_OK;
}

/// <summary>
/// Unlock the previously locked frame.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::UnlockFrame()
{
    AssertOtherThread();

    LeaveCriticalSection(&m_lockFrame);

    return S_OK;
}

///////////////////////////////////////////////////////////////////////////////////////////

/// <summary>
/// Initialize Kinect Fusion volume and images for processing
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::InitializeKinectFusion()
{
    AssertOwnThread();

    HRESULT hr = S_OK;

    hr = m_frame.Initialize(m_paramsCurrent.m_cDepthImagePixels);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Failed to allocate frame buffers.");
        return hr;
    }

    // Check to ensure suitable DirectX11 compatible hardware exists before initializing Kinect Fusion
    WCHAR description[MAX_PATH];
    WCHAR instancePath[MAX_PATH];

    if (FAILED(hr = NuiFusionGetDeviceInfo(
        m_paramsCurrent.m_processorType, 
        m_paramsCurrent.m_deviceIndex, 
        &description[0], 
        ARRAYSIZE(description), 
        &instancePath[0],
        ARRAYSIZE(instancePath), 
        &m_frame.m_deviceMemory)))
    {
        if (hr ==  E_NUI_BADINDEX)
        {
            // This error code is returned either when the device index is out of range for the processor 
            // type or there is no DirectX11 capable device installed. As we set -1 (auto-select default) 
            // for the device index in the parameters, this indicates that there is no DirectX11 capable 
            // device. The options for users in this case are to either install a DirectX11 capable device
            // (see documentation for recommended GPUs) or to switch to non-real-time CPU based 
            // reconstruction by changing the processor type to NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_CPU.
            SetStatusMessage(L"No DirectX11 device detected, or invalid device index - Kinect Fusion requires a DirectX11 device for GPU-based reconstruction.");
        }
        else
        {
            SetStatusMessage(L"Failed in call to NuiFusionGetDeviceInfo.");
        }
        return hr;
    }

    unsigned int width = static_cast<UINT>(m_paramsCurrent.m_cDepthWidth);
    unsigned int height = static_cast<UINT>(m_paramsCurrent.m_cDepthHeight);

    unsigned int colorWidth = static_cast<UINT>(m_paramsCurrent.m_cColorWidth);
    unsigned int colorHeight = static_cast<UINT>(m_paramsCurrent.m_cColorHeight);

    // Calculate the down sampled image sizes, which are used for the AlignPointClouds calculation frames
    unsigned int downsampledWidth = width / m_paramsCurrent.m_cAlignPointCloudsImageDownsampleFactor;
    unsigned int downsampledHeight = height / m_paramsCurrent.m_cAlignPointCloudsImageDownsampleFactor;

    // Frame generated from the depth input
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, width, height, &m_pDepthFloatImage)))
    {
        return hr;
    }

    // Frames generated from the depth input
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, downsampledWidth, downsampledHeight, &m_pDownsampledDepthFloatImage)))
    {
        return hr;
    }

    // Frame generated from the raw color input of Kinect
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, colorWidth, colorHeight, &m_pColorImage)))
    {
        return hr;
    }

    // Frame generated from the raw color input of Kinect for use in the camera pose finder.
    // Note color will be down-sampled to the depth size if depth and color capture resolutions differ.
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height, &m_pResampledColorImage)))
    {
        return hr;
    }

    // Frame re-sampled from the color input of Kinect, aligned to depth - this will be the same size as the depth.
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height, &m_pResampledColorImageDepthAligned)))
    {
        return hr;
    }

    // Point Cloud generated from ray-casting the volume
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_POINT_CLOUD, width, height, &m_pRaycastPointCloud)))
    {
        return hr;
    }

    // Point Cloud generated from ray-casting the volume
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_POINT_CLOUD, downsampledWidth, downsampledHeight, &m_pDownsampledRaycastPointCloud)))
    {
        return hr;
    }

    // Depth frame generated from ray-casting the volume
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, width, height, &m_pRaycastDepthFloatImage)))
    {
        return hr;
    }

    // Image of the raycast Volume to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height, &m_pShadedSurface)))
    {
        return hr;
    }

    // Image of the raycast Volume with surface normals to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height,  &m_pShadedSurfaceNormals)))
    {
        return hr;
    }

    // Image of the raycast Volume with the captured color to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height, &m_pCapturedSurfaceColor)))
    {
        return hr;
    }

    // Image of the camera tracking deltas to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, width, height, &m_pFloatDeltaFromReference)))
    {
        return hr;
    }

    // Image of the camera tracking deltas to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, width, height, &m_pShadedDeltaFromReference)))
    {
        return hr;
    }

    // Image of the camera tracking deltas to display
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_COLOR, downsampledWidth, downsampledHeight, &m_pDownsampledShadedDeltaFromReference)))
    {
        return hr;
    }

    // Image from input depth for use with AlignPointClouds call
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, width, height, &m_pSmoothDepthFloatImage)))
    {
        return hr;
    }

    // Frames generated from smoothing the depth input
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_FLOAT, downsampledWidth, downsampledHeight, &m_pDownsampledSmoothDepthFloatImage)))
    {
        return hr;
    }

    // Image used in post pose finding success check AlignPointClouds call
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_POINT_CLOUD, width, height, &m_pDepthPointCloud)))
    {
        return hr;
    }

    // Point Cloud generated from depth input, in local camera coordinate system
    if (FAILED(hr = CreateFrame(NUI_FUSION_IMAGE_TYPE_POINT_CLOUD, downsampledWidth, downsampledHeight, &m_pDownsampledDepthPointCloud)))
    {
        return hr;
    }

    if (nullptr != m_pDepthImagePixelBuffer)
    {
        // If buffer length has changed, delete the old one.
        if (m_paramsCurrent.m_cDepthImagePixels != m_cPixelBufferLength)
        {
            SAFE_DELETE_ARRAY(m_pDepthImagePixelBuffer);
        }
    }

    if (nullptr == m_pDepthImagePixelBuffer)
    {
        // Depth pixel array to capture data from Kinect sensor
        m_pDepthImagePixelBuffer =
            new(std::nothrow) NUI_DEPTH_IMAGE_PIXEL[m_paramsCurrent.m_cDepthImagePixels];

        if (nullptr == m_pDepthImagePixelBuffer)
        {
            SetStatusMessage(L"Failed to initialize Kinect Fusion depth image pixel buffer.");
            return hr;
        }

        m_cPixelBufferLength = m_paramsCurrent.m_cDepthImagePixels;
    }

    if (nullptr != m_pColorCoordinates)
    {
        // If buffer length has changed, delete the old one.
        if (m_paramsCurrent.m_cDepthImagePixels != m_cColorCoordinateBufferLength)
        {
            SAFE_DELETE_ARRAY(m_pColorCoordinates);
        }
    }

    if (nullptr == m_pColorCoordinates)
    {
        // Color coordinate array to capture data from Kinect sensor and for color to depth mapping
        // Note: this must be the same size as the depth
        m_pColorCoordinates = 
            new(std::nothrow) NUI_COLOR_IMAGE_POINT[m_paramsCurrent.m_cDepthImagePixels];

        if (nullptr == m_pColorCoordinates)
        {
            SetStatusMessage(L"Failed to initialize Kinect Fusion color image coordinate buffers.");
            return hr;
        }

        m_cColorCoordinateBufferLength = m_paramsCurrent.m_cDepthImagePixels;
    }

    if (nullptr != m_pCameraPoseFinder)
    {
        SafeRelease(m_pCameraPoseFinder);
    }

    // Create the camera pose finder if necessary
    if (nullptr == m_pCameraPoseFinder)
    {
        NUI_FUSION_CAMERA_POSE_FINDER_PARAMETERS cameraPoseFinderParameters;

        cameraPoseFinderParameters.featureSampleLocationsPerFrameCount = m_paramsCurrent.m_cCameraPoseFinderFeatureSampleLocationsPerFrame;
        cameraPoseFinderParameters.maxPoseHistoryCount = m_paramsCurrent.m_cMaxCameraPoseFinderPoseHistory;
        cameraPoseFinderParameters.maxDepthThreshold = m_paramsCurrent.m_fMaxCameraPoseFinderDepthThreshold;

        if (FAILED(hr = NuiFusionCreateCameraPoseFinder(
            &cameraPoseFinderParameters,
            nullptr,
            &m_pCameraPoseFinder)))
        {
            return hr;
        }
    }

    return hr;
}

HRESULT KinectFusionProcessor::CreateFrame(
    NUI_FUSION_IMAGE_TYPE frameType,
    unsigned int imageWidth,
    unsigned int imageHeight,
    NUI_FUSION_IMAGE_FRAME** ppImageFrame)
{
    HRESULT hr = S_OK;
    
    if (nullptr != *ppImageFrame)
    {
        // If image size or type has changed, release the old one.
        if ((*ppImageFrame)->width != imageWidth ||
            (*ppImageFrame)->height != imageHeight ||
            (*ppImageFrame)->imageType != frameType)
        {
            static_cast<void>(NuiFusionReleaseImageFrame(*ppImageFrame));
            *ppImageFrame = nullptr;
        }
    }

    // Create a new frame as needed.
    if (nullptr == *ppImageFrame)
    {
        hr = NuiFusionCreateImageFrame(
            frameType,
            imageWidth,
            imageHeight,
            nullptr,
            ppImageFrame);

        if (FAILED(hr))
        {
            SetStatusMessage(L"Failed to initialize Kinect Fusion image.");
        }
    }

    return hr;
}

/// <summary>
/// Release and re-create a Kinect Fusion Reconstruction Volume
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::RecreateVolume()
{
    AssertOwnThread();

    HRESULT hr = S_OK;

    // Clean up Kinect Fusion
    SafeRelease(m_pVolume);

    SetIdentityMatrix(m_worldToCameraTransform);

    // Create the Kinect Fusion Reconstruction Volume
    // Here we create a color volume, enabling optional color processing in the Integrate, ProcessFrame and CalculatePointCloud calls
    hr = NuiFusionCreateColorReconstruction(
        &m_paramsCurrent.m_reconstructionParams,
        m_paramsCurrent.m_processorType,
        m_paramsCurrent.m_deviceIndex,
        &m_worldToCameraTransform,
        &m_pVolume);

    if (FAILED(hr))
    {
        if (E_NUI_GPU_FAIL == hr)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Device %d not able to run Kinect Fusion, or error initializing.", m_paramsCurrent.m_deviceIndex);
            SetStatusMessage(buf);
        }
        else if (E_NUI_GPU_OUTOFMEMORY == hr)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Device %d out of memory error initializing reconstruction - try a smaller reconstruction volume.", m_paramsCurrent.m_deviceIndex);
            SetStatusMessage(buf);
        }
        else if (NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_CPU != m_paramsCurrent.m_processorType)
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Failed to initialize Kinect Fusion reconstruction volume on device %d.", m_paramsCurrent.m_deviceIndex);
            SetStatusMessage(buf);
        }
        else
        {
            WCHAR buf[MAX_PATH];
            swprintf_s(buf, ARRAYSIZE(buf), L"Failed to initialize Kinect Fusion reconstruction volume on CPU %d.", m_paramsCurrent.m_deviceIndex);
            SetStatusMessage(buf);
        }

        return hr;
    }
    else
    {
        // Save the default world to volume transformation to be optionally used in ResetReconstruction
        hr = m_pVolume->GetCurrentWorldToVolumeTransform(&m_defaultWorldToVolumeTransform);
        if (FAILED(hr))
        {
            SetStatusMessage(L"Failed in call to GetCurrentWorldToVolumeTransform.");
            return hr;
        }

        if (m_paramsCurrent.m_bTranslateResetPoseByMinDepthThreshold)
        {
            // This call will set the world-volume transformation
            hr = InternalResetReconstruction();
            if (FAILED(hr))
            {
                return hr;
            }
        }
        else
        {
            // Reset pause and signal that the integration resumed
            ResetTracking();
        }

        // Map X axis to blue channel, Y axis to green channel and Z axis to red channel,
        // normalizing each to the range [0, 1].
        SetIdentityMatrix(m_worldToBGRTransform);
        m_worldToBGRTransform.M11 = m_paramsCurrent.m_reconstructionParams.voxelsPerMeter / m_paramsCurrent.m_reconstructionParams.voxelCountX;
        m_worldToBGRTransform.M22 = m_paramsCurrent.m_reconstructionParams.voxelsPerMeter / m_paramsCurrent.m_reconstructionParams.voxelCountY;
        m_worldToBGRTransform.M33 = m_paramsCurrent.m_reconstructionParams.voxelsPerMeter / m_paramsCurrent.m_reconstructionParams.voxelCountZ;
        m_worldToBGRTransform.M41 = 0.5f;
        m_worldToBGRTransform.M42 = 0.5f;
        m_worldToBGRTransform.M44 = 1.0f;

        SetStatusMessage(L"Reconstruction has been reset.");
    }

    return hr;
}

/// <summary>
/// Get Extended depth data
/// </summary>
/// <param name="imageFrame">The extended depth image frame to copy.</param>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::CopyExtendedDepth(NUI_IMAGE_FRAME &imageFrame)
{
    AssertOwnThread();

    HRESULT hr = S_OK;

    if (nullptr == m_pDepthImagePixelBuffer)
    {
        SetStatusMessage(L"Error depth image pixel buffer is nullptr.");
        return E_FAIL;
    }

    INuiFrameTexture *extendedDepthTex = nullptr;

    // Extract the extended depth in NUI_DEPTH_IMAGE_PIXEL format from the frame
    BOOL nearModeOperational = FALSE;
    hr = m_pNuiSensor->NuiImageFrameGetDepthImagePixelFrameTexture(
        m_pDepthStreamHandle,
        &imageFrame,
        &nearModeOperational,
        &extendedDepthTex);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Error getting extended depth texture.");
        return hr;
    }

    NUI_LOCKED_RECT extendedDepthLockedRect;

    // Lock the frame data to access the un-clamped NUI_DEPTH_IMAGE_PIXELs
    hr = extendedDepthTex->LockRect(0, &extendedDepthLockedRect, nullptr, 0);

    if (FAILED(hr) || extendedDepthLockedRect.Pitch == 0)
    {
        SetStatusMessage(L"Error getting extended depth texture pixels.");
        return hr;
    }

    // Copy the depth pixels so we can return the image frame
    errno_t err = memcpy_s(
        m_pDepthImagePixelBuffer,
        m_paramsCurrent.m_cDepthImagePixels * sizeof(NUI_DEPTH_IMAGE_PIXEL),
        extendedDepthLockedRect.pBits,
        extendedDepthTex->BufferLen());

    extendedDepthTex->UnlockRect(0);

    if (0 != err)
    {
        SetStatusMessage(L"Error copying extended depth texture pixels.");
        return hr;
    }

    return hr;
}

/// <summary>
/// Get Color data
/// </summary>
/// <param name="imageFrame">The color image frame to copy.</param>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::CopyColor(NUI_IMAGE_FRAME &imageFrame)
{
    HRESULT hr = S_OK;

    if (nullptr == m_pColorImage)
    {
        SetStatusMessage(L"Error copying color texture pixels.");
        return E_FAIL;
    }

    INuiFrameTexture *srcColorTex = imageFrame.pFrameTexture;
    INuiFrameTexture *destColorTex = m_pColorImage->pFrameTexture;

    if (nullptr == srcColorTex || nullptr == destColorTex)
    {
        return E_NOINTERFACE;
    }

    // Lock the frame data to access the color pixels
    NUI_LOCKED_RECT srcLockedRect;

    hr = srcColorTex->LockRect(0, &srcLockedRect, nullptr, 0);

    if (FAILED(hr) || srcLockedRect.Pitch == 0)
    {
        SetStatusMessage(L"Error getting color texture pixels.");
        return E_NOINTERFACE;
    }

    // Lock the frame data to access the color pixels
    NUI_LOCKED_RECT destLockedRect;

    hr = destColorTex->LockRect(0, &destLockedRect, nullptr, 0);

    if (FAILED(hr) || destLockedRect.Pitch == 0)
    {
        srcColorTex->UnlockRect(0);
        SetStatusMessage(L"Error copying color texture pixels.");
        return E_NOINTERFACE;
    }

    // Copy the color pixels so we can return the image frame
    errno_t err = memcpy_s(
        destLockedRect.pBits, 
        m_paramsCurrent.m_cColorImagePixels * KinectFusionParams::BytesPerPixel,
        srcLockedRect.pBits,
        srcLockedRect.size);

    srcColorTex->UnlockRect(0);
    destColorTex->UnlockRect(0);

    if (0 != err)
    {
        SetStatusMessage(L"Error copying color texture pixels.");
        hr = E_FAIL;
    }

    return hr;
}

/// <summary>
/// Adjust color to the same space as depth
/// </summary>
/// <returns>S_OK for success, or failure code</returns>
HRESULT KinectFusionProcessor::MapColorToDepth()
{
    HRESULT hr;

    if (nullptr == m_pColorImage || nullptr == m_pResampledColorImageDepthAligned 
        || nullptr == m_pDepthImagePixelBuffer || nullptr == m_pColorCoordinates)
    {
        return E_FAIL;
    }

    INuiFrameTexture *srcColorTex = m_pColorImage->pFrameTexture;
    INuiFrameTexture *destColorTex = m_pResampledColorImageDepthAligned->pFrameTexture;

    if (nullptr == srcColorTex || nullptr == destColorTex)
    {
        SetStatusMessage(L"Error accessing color textures.");
        return E_NOINTERFACE;
    }

    // Lock the source color frame
    NUI_LOCKED_RECT srcLockedRect;

    // Lock the frame data to access the color pixels
    hr = srcColorTex->LockRect(0, &srcLockedRect, nullptr, 0);

    if (FAILED(hr) || srcLockedRect.Pitch == 0)
    {
        SetStatusMessage(L"Error accessing color texture pixels.");
        return  E_FAIL;
    }

    // Lock the destination color frame
    NUI_LOCKED_RECT destLockedRect;

    // Lock the frame data to access the color pixels
    hr = destColorTex->LockRect(0, &destLockedRect, nullptr, 0);

    if (FAILED(hr) || destLockedRect.Pitch == 0)
    {
        srcColorTex->UnlockRect(0);
        SetStatusMessage(L"Error accessing color texture pixels.");
        return  E_FAIL;
    }

    int *rawColorData = reinterpret_cast<int*>(srcLockedRect.pBits);
    int *colorDataInDepthFrame = reinterpret_cast<int*>(destLockedRect.pBits);

    // Get the coordinates to convert color to depth space
    hr = m_pMapper->MapDepthFrameToColorFrame(
        m_paramsCurrent.m_depthImageResolution, 
        m_paramsCurrent.m_cDepthImagePixels, 
        m_pDepthImagePixelBuffer, 
        NUI_IMAGE_TYPE_COLOR, 
        m_paramsCurrent.m_colorImageResolution, 
        m_paramsCurrent.m_cDepthImagePixels,   // the color coordinates that get set are the same array size as the depth image
        m_pColorCoordinates );

    if (FAILED(hr))
    {
        srcColorTex->UnlockRect(0);
        destColorTex->UnlockRect(0);
        return hr;
    }

    // Loop over each row and column of the destination color image and copy from the source image
    // Note that we could also do this the other way, and convert the depth pixels into the color space, 
    // avoiding black areas in the converted color image and repeated color images in the background
    // However, then the depth would have radial and tangential distortion like the color camera image,
    // which is not ideal for Kinect Fusion reconstruction.
    if (m_paramsCurrent.m_bMirrorDepthFrame)
    {
        Concurrency::parallel_for(0, static_cast<int>(m_paramsCurrent.m_cDepthHeight), [&](int y)
        {
            unsigned int destIndex = y * m_paramsCurrent.m_cDepthWidth;

            for (int x = 0; x < m_paramsCurrent.m_cDepthWidth; ++x, ++destIndex)
            {
                // calculate index into depth array
                int colorInDepthX = m_pColorCoordinates[destIndex].x;
                int colorInDepthY = m_pColorCoordinates[destIndex].y;

                // make sure the depth pixel maps to a valid point in color space
                if ( colorInDepthX >= 0 && colorInDepthX < m_paramsCurrent.m_cColorWidth 
                    && colorInDepthY >= 0 && colorInDepthY < m_paramsCurrent.m_cColorHeight 
                    && m_pDepthImagePixelBuffer[destIndex].depth != 0)
                {
                    // Calculate index into color array
                    unsigned int sourceColorIndex = colorInDepthX + (colorInDepthY * m_paramsCurrent.m_cColorWidth);

                    // Copy color pixel
                    colorDataInDepthFrame[destIndex] = rawColorData[sourceColorIndex];
                }
                else
                {
                    colorDataInDepthFrame[destIndex] = 0;
                }
            }
        });
    }
    else
    {
        Concurrency::parallel_for(0, static_cast<int>(m_paramsCurrent.m_cDepthHeight), [&](int y)
        {
            unsigned int destIndex = y * m_paramsCurrent.m_cDepthWidth;

            // Horizontal flip the color image as the standard depth image is flipped internally in Kinect Fusion
            // to give a viewpoint as though from behind the Kinect looking forward by default.
            unsigned int flippedDestIndex = destIndex + (m_paramsCurrent.m_cDepthWidth-1);

            for (int x = 0; x < m_paramsCurrent.m_cDepthWidth; ++x, ++destIndex, --flippedDestIndex)
            {
                // calculate index into depth array
                int colorInDepthX = m_pColorCoordinates[destIndex].x;
                int colorInDepthY = m_pColorCoordinates[destIndex].y;

                // make sure the depth pixel maps to a valid point in color space
                if ( colorInDepthX >= 0 && colorInDepthX < m_paramsCurrent.m_cColorWidth 
                    && colorInDepthY >= 0 && colorInDepthY < m_paramsCurrent.m_cColorHeight 
                    && m_pDepthImagePixelBuffer[destIndex].depth != 0)
                {
                    // Calculate index into color array- this will perform a horizontal flip as well
                    unsigned int sourceColorIndex = colorInDepthX + (colorInDepthY * m_paramsCurrent.m_cColorWidth);

                    // Copy color pixel
                    colorDataInDepthFrame[flippedDestIndex] = rawColorData[sourceColorIndex];
                }
                else
                {
                    colorDataInDepthFrame[flippedDestIndex] = 0;
                }
            }
        });
    }

    srcColorTex->UnlockRect(0);
    destColorTex->UnlockRect(0);

    return hr;
}

/// <summary>
/// Get the next frames from Kinect, re-synchronizing depth with color if required.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::GetKinectFrames(bool &colorSynchronized)
{
    NUI_IMAGE_FRAME imageFrame;
    LONGLONG currentDepthFrameTime = 0;
    LONGLONG currentColorFrameTime = 0;
    colorSynchronized = true;   // assume we are synchronized to start with

    ////////////////////////////////////////////////////////
    // Get an extended depth frame from Kinect

    HRESULT hr = m_pNuiSensor->NuiImageStreamGetNextFrame(m_pDepthStreamHandle, 0, &imageFrame);
    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect depth stream NuiImageStreamGetNextFrame call failed.");
        return hr;
    }

    hr = CopyExtendedDepth(imageFrame);

    currentDepthFrameTime = imageFrame.liTimeStamp.QuadPart;

    // Release the Kinect camera frame
    m_pNuiSensor->NuiImageStreamReleaseFrame(m_pDepthStreamHandle, &imageFrame);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect depth stream NuiImageStreamReleaseFrame call failed.");
        return hr;
    }

    ////////////////////////////////////////////////////////
    // Get a color frame from Kinect

    currentColorFrameTime = m_cLastColorFrameTimeStamp;

    hr = m_pNuiSensor->NuiImageStreamGetNextFrame(m_pColorStreamHandle, 0, &imageFrame);
    if (FAILED(hr))
    {
        // Here we just do not integrate color rather than reporting an error
        colorSynchronized = false;
    }
    else
    {
        hr = CopyColor(imageFrame);

        currentColorFrameTime = imageFrame.liTimeStamp.QuadPart;

        // Release the Kinect camera frame
        m_pNuiSensor->NuiImageStreamReleaseFrame(m_pColorStreamHandle, &imageFrame);

        if (FAILED(hr))
        {
            SetStatusMessage(L"Kinect color stream NuiImageStreamReleaseFrame call failed.");
        }
    }


    // Check color and depth frame timestamps to ensure they were captured at the same time
    // If not, we attempt to re-synchronize by getting a new frame from the stream that is behind.
    int timestampDiff = static_cast<int>(abs(currentColorFrameTime - currentDepthFrameTime));

    if (timestampDiff >= cMinTimestampDifferenceForFrameReSync && m_cSuccessfulFrameCounter > 0 && (m_paramsCurrent.m_bAutoFindCameraPoseWhenLost || m_paramsCurrent.m_bCaptureColor))
    {
        // Get another frame to try and re-sync
        if (currentColorFrameTime - currentDepthFrameTime >= cMinTimestampDifferenceForFrameReSync)
        {
            // Perform camera tracking only from this current depth frame
            if (nullptr != m_pVolume)
            {
                // Convert the pixels describing extended depth as unsigned short type in millimeters to depth
                // as floating point type in meters.
                hr = m_pVolume->DepthToDepthFloatFrame(
                            m_pDepthImagePixelBuffer,
                            m_paramsCurrent.m_cDepthImagePixels * sizeof(NUI_DEPTH_IMAGE_PIXEL),
                            m_pDepthFloatImage,
                            m_paramsCurrent.m_fMinDepthThreshold,
                            m_paramsCurrent.m_fMaxDepthThreshold,
                            m_paramsCurrent.m_bMirrorDepthFrame);

                if (FAILED(hr))
                {
                    SetStatusMessage(L"Kinect Fusion NuiFusionDepthToDepthFloatFrame call failed.");
                    return hr;
                }

                Matrix4 calculatedCameraPose = m_worldToCameraTransform;
                FLOAT alignmentEnergy = 1.0f;

                hr = TrackCameraAlignPointClouds(calculatedCameraPose, alignmentEnergy);

                if (SUCCEEDED(hr))
                {
                    m_worldToCameraTransform = calculatedCameraPose;

                    // Raycast and set reference frame for tracking with AlignDepthFloatToReconstruction
                    hr = SetReferenceFrame(m_worldToCameraTransform);

                    SetTrackingSucceeded();
                }
                else
                {
                    SetTrackingFailed();
                }
            }

            // Get another depth frame to try and re-sync as color ahead of depth
            hr = m_pNuiSensor->NuiImageStreamGetNextFrame(m_pDepthStreamHandle, timestampDiff, &imageFrame);
            if (FAILED(hr))
            {
                // Return silently, having performed camera tracking on the current depth frame
                return hr;
            }

            hr = CopyExtendedDepth(imageFrame);

            currentDepthFrameTime = imageFrame.liTimeStamp.QuadPart;

            // Release the Kinect camera frame
            m_pNuiSensor->NuiImageStreamReleaseFrame(m_pDepthStreamHandle, &imageFrame);

            if (FAILED(hr))
            {
                SetStatusMessage(L"Kinect depth stream NuiImageStreamReleaseFrame call failed.");
                return hr;
            }
        }
        else if (currentDepthFrameTime - currentColorFrameTime >= cMinTimestampDifferenceForFrameReSync && WaitForSingleObject(m_hNextColorFrameEvent, 0) != WAIT_TIMEOUT)
        {
            // Get another color frame to try and re-sync as depth ahead of color and there is another color frame waiting
            hr = m_pNuiSensor->NuiImageStreamGetNextFrame(m_pColorStreamHandle, 0, &imageFrame);
            if (FAILED(hr))
            {
                // Here we just do not integrate color rather than reporting an error
                colorSynchronized = false;
            }
            else
            {
                hr = CopyColor(imageFrame);

                currentColorFrameTime = imageFrame.liTimeStamp.QuadPart;

                // Release the Kinect camera frame
                m_pNuiSensor->NuiImageStreamReleaseFrame(m_pColorStreamHandle, &imageFrame);

                if (FAILED(hr))
                {
                    SetStatusMessage(L"Kinect color stream NuiImageStreamReleaseFrame call failed.");
                    return hr;
                }
            }
        }

        timestampDiff = static_cast<int>(abs(currentColorFrameTime - currentDepthFrameTime));

        // If the difference is still too large, we do not want to integrate color
        if (timestampDiff > cMinTimestampDifferenceForFrameReSync || FAILED(hr))
        {
            colorSynchronized = false;
        }
        else
        {
            colorSynchronized = true;
        }
    }

    ////////////////////////////////////////////////////////
    // To enable playback of a .xed file through Kinect Studio and reset of the reconstruction
    // if the .xed loops, we test for when the frame timestamp has skipped a large number. 
    // Note: this will potentially continually reset live reconstructions on slow machines which
    // cannot process a live frame in less time than the reset threshold. Increase the number of
    // milliseconds in cResetOnTimeStampSkippedMilliseconds if this is a problem.

    int cResetOnTimeStampSkippedMilliseconds = cResetOnTimeStampSkippedMillisecondsGPU;

    if (m_paramsCurrent.m_processorType == NUI_FUSION_RECONSTRUCTION_PROCESSOR_TYPE_CPU)
    {
        cResetOnTimeStampSkippedMilliseconds = cResetOnTimeStampSkippedMillisecondsCPU;
    }

    if (m_paramsCurrent.m_bAutoResetReconstructionOnTimeout && m_cFrameCounter != 0 && nullptr != m_pVolume 
        && abs(currentDepthFrameTime - m_cLastDepthFrameTimeStamp) > cResetOnTimeStampSkippedMilliseconds)
    {
        hr = InternalResetReconstruction();

        if (SUCCEEDED(hr))
        {
            SetStatusMessage(L"Reconstruction has been reset.");
        }
        else
        {
            SetStatusMessage(L"Failed to reset reconstruction.");
        }
    }

    m_cLastDepthFrameTimeStamp = currentDepthFrameTime;
    m_cLastColorFrameTimeStamp = currentColorFrameTime;

    return hr;
}

/// <summary>
/// Perform camera tracking using AlignPointClouds
/// </summary>
HRESULT KinectFusionProcessor::TrackCameraAlignPointClouds(Matrix4 &calculatedCameraPose, FLOAT &alignmentEnergy)
{
    ////////////////////////////////////////////////////////
    // Down sample the depth image

    HRESULT hr = DownsampleFrameNearestNeighbor(
        m_pDepthFloatImage, 
        m_pDownsampledDepthFloatImage,
        m_paramsCurrent.m_cAlignPointCloudsImageDownsampleFactor);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion DownsampleFrameNearestNeighbor call failed.");
        return hr;
    }

    ////////////////////////////////////////////////////////
    // Smooth depth image

    hr = m_pVolume->SmoothDepthFloatFrame(
        m_pDownsampledDepthFloatImage, 
        m_pDownsampledSmoothDepthFloatImage, 
        m_paramsCurrent.m_cSmoothingKernelWidth, 
        m_paramsCurrent.m_fSmoothingDistanceThreshold);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion SmoothDepth call failed.");
        return hr;
    }

    ////////////////////////////////////////////////////////
    // Calculate Point Cloud from smoothed input Depth Image

    hr = NuiFusionDepthFloatFrameToPointCloud(
        m_pDownsampledSmoothDepthFloatImage,
        m_pDownsampledDepthPointCloud);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion NuiFusionDepthFloatFrameToPointCloud call failed.");
        return hr;
    }

    ////////////////////////////////////////////////////////
    // CalculatePointCloud

    // Raycast even if camera tracking failed, to enable us to visualize what is 
    // happening with the system
    hr = m_pVolume->CalculatePointCloud(
        m_pDownsampledRaycastPointCloud,
        nullptr, 
        &calculatedCameraPose);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion CalculatePointCloud call failed.");
        return hr;
    }

    ////////////////////////////////////////////////////////
    // Call AlignPointClouds

    HRESULT tracking = S_OK;

    // Only calculate the residual delta from reference frame every m_cDeltaFromReferenceFrameCalculationInterval
    // frames to reduce computation time
    if (m_bCalculateDeltaFrame)
    {
        tracking = NuiFusionAlignPointClouds(
            m_pDownsampledRaycastPointCloud,
            m_pDownsampledDepthPointCloud,
            NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT,
            m_pDownsampledShadedDeltaFromReference,
            &calculatedCameraPose); 

        // Up sample the delta from reference image to display as the original resolution
        hr = UpsampleFrameNearestNeighbor(
            m_pDownsampledShadedDeltaFromReference, 
            m_pShadedDeltaFromReference, 
            m_paramsCurrent.m_cAlignPointCloudsImageDownsampleFactor);

        if (FAILED(hr))
        {
            SetStatusMessage(L"Kinect Fusion UpsampleFrameNearestNeighbor call failed.");
            return hr;
        }
    }
    else
    {
        tracking = NuiFusionAlignPointClouds(
            m_pDownsampledRaycastPointCloud,
            m_pDownsampledDepthPointCloud,
            NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT,
            nullptr,
            &calculatedCameraPose); 
    }

    if (!FAILED(tracking))
    {
        // Perform additional transform magnitude check
        // Camera Tracking has converged but did we get a sensible pose estimate?
        // see if relative rotation and translation exceed thresholds 
        if (CameraTransformFailed(
            m_worldToCameraTransform,
            calculatedCameraPose,
            m_paramsCurrent.m_fMaxTranslationDelta,
            m_paramsCurrent.m_fMaxRotationDelta))
        {
            // We calculated too large a move for this to be a sensible estimate,
            // quite possibly the camera tracking drifted. Force camera pose finding.
            hr = E_NUI_FUSION_TRACKING_ERROR;

            SetStatusMessage(
                L"Kinect Fusion AlignPointClouds camera tracking failed "
                L"in transform magnitude check!");
        }
    }
    else
    {
        hr = tracking;
    }

    return hr;
}

/// <summary>
/// Perform camera tracking using AlignDepthFloatToReconstruction
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::TrackCameraAlignDepthFloatToReconstruction(Matrix4 &calculatedCameraPose, FLOAT &alignmentEnergy)
{
    HRESULT hr = S_OK;

    // Only calculate the residual delta from reference frame every m_cDeltaFromReferenceFrameCalculationInterval
    // frames to reduce computation time
    HRESULT tracking = S_OK;

    if (m_bCalculateDeltaFrame)
    {
        tracking = m_pVolume->AlignDepthFloatToReconstruction(
            m_pDepthFloatImage,
            NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT,
            m_pFloatDeltaFromReference,
            &alignmentEnergy,
            &calculatedCameraPose);
    }
    else
    {
        tracking = m_pVolume->AlignDepthFloatToReconstruction(
            m_pDepthFloatImage,
            NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT,
            nullptr,
            &alignmentEnergy,
            &calculatedCameraPose);
    }

    bool trackingSuccess = !(FAILED(tracking) || alignmentEnergy > m_paramsCurrent.m_fMaxAlignToReconstructionEnergyForSuccess || (alignmentEnergy == 0.0f && m_cSuccessfulFrameCounter > 1));

    if (trackingSuccess)
    {
        // Get the camera pose
        m_pVolume->GetCurrentWorldToCameraTransform(&calculatedCameraPose);
    }
    else
    {
        if (FAILED(tracking))
        {
            hr = tracking;
        }
        else
        {
            // We failed in the energy check
            hr = E_NUI_FUSION_TRACKING_ERROR;
        }
    }

    return hr;
}

/// <summary>
/// Handle new depth data and perform Kinect Fusion processing
/// </summary>
void KinectFusionProcessor::ProcessDepth()
{
    AssertOwnThread();

    HRESULT hr = S_OK;
    bool depthAvailable = false;
    bool raycastFrame = false;
    bool cameraPoseFinderAvailable = IsCameraPoseFinderAvailable();
    bool integrateColor = m_paramsCurrent.m_bCaptureColor && m_cFrameCounter % m_paramsCurrent.m_cColorIntegrationInterval == 0;
    bool colorSynchronized = false;
    FLOAT alignmentEnergy = 1.0f;
    Matrix4 calculatedCameraPose = m_worldToCameraTransform;
    m_bCalculateDeltaFrame = (m_cFrameCounter % m_paramsCurrent.m_cDeltaFromReferenceFrameCalculationInterval == 0) 
                            || (m_bTrackingHasFailedPreviously && m_cSuccessfulFrameCounter <= 2);

    // Get the next frames from Kinect
    hr = GetKinectFrames(colorSynchronized);

    if (FAILED(hr))
    {
        goto FinishFrame;
    }

    // Only integrate when color is synchronized with depth
    integrateColor = integrateColor && colorSynchronized;

    ////////////////////////////////////////////////////////
    // Depth to Depth Float

    // Convert the pixels describing extended depth as unsigned short type in millimeters to depth
    // as floating point type in meters.
    if (nullptr == m_pVolume)
    {
        hr =  NuiFusionDepthToDepthFloatFrame(
            m_pDepthImagePixelBuffer,
            m_paramsCurrent.m_cDepthWidth,
            m_paramsCurrent.m_cDepthHeight,
            m_pDepthFloatImage,
            m_paramsCurrent.m_fMinDepthThreshold,
            m_paramsCurrent.m_fMaxDepthThreshold,
            m_paramsCurrent.m_bMirrorDepthFrame);
    }
    else
    {
        hr = m_pVolume->DepthToDepthFloatFrame(
                m_pDepthImagePixelBuffer,
                m_paramsCurrent.m_cDepthImagePixels * sizeof(NUI_DEPTH_IMAGE_PIXEL),
                m_pDepthFloatImage,
                m_paramsCurrent.m_fMinDepthThreshold,
                m_paramsCurrent.m_fMaxDepthThreshold,
                m_paramsCurrent.m_bMirrorDepthFrame);
    }

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion NuiFusionDepthToDepthFloatFrame call failed.");
        goto FinishFrame;
    }

    depthAvailable = true;

    // Return if the volume is not initialized, just drawing the depth image
    if (nullptr == m_pVolume)
    {
        SetStatusMessage(
            L"Kinect Fusion reconstruction volume not initialized. "
            L"Please try reducing volume size or restarting.");
        goto FinishFrame;
    }

    ////////////////////////////////////////////////////////
    // Perform Camera Tracking

    HRESULT tracking = E_NUI_FUSION_TRACKING_ERROR;

    if (!m_bTrackingFailed && 0 != m_cFrameCounter)
    {
        // Here we can either call or TrackCameraAlignDepthFloatToReconstruction or TrackCameraAlignPointClouds
        // The TrackCameraAlignPointClouds function typically has higher performance with the camera pose finder 
        // due to its wider basin of convergence, enabling it to more robustly regain tracking from nearby poses
        // suggested by the camera pose finder after tracking is lost.
        if (m_paramsCurrent.m_bAutoFindCameraPoseWhenLost)
        {
            tracking = TrackCameraAlignPointClouds(calculatedCameraPose, alignmentEnergy);
        }
        else
        {
            // If the camera pose finder is not turned on, we use AlignDepthFloatToReconstruction
            tracking = TrackCameraAlignDepthFloatToReconstruction(calculatedCameraPose, alignmentEnergy);
        }
    }

    if (FAILED(tracking) && 0 != m_cFrameCounter)   // frame 0 always succeeds
    {
        SetTrackingFailed();

        if (!cameraPoseFinderAvailable)
        {
            if (tracking == E_NUI_FUSION_TRACKING_ERROR)
            {
                WCHAR str[MAX_PATH];
                swprintf_s(str, ARRAYSIZE(str), L"Kinect Fusion camera tracking FAILED! Align the camera to the last tracked position.");
                SetStatusMessage(str);
            }
            else
            {
                SetStatusMessage(L"Kinect Fusion camera tracking call failed!");
                goto FinishFrame;
            }
        }
        else
        {
            // Here we try to find the correct camera pose, to re-localize camera tracking.
            // We can call either the version using AlignDepthFloatToReconstruction or the version 
            // using AlignPointClouds, which typically has a higher success rate with the camera pose finder.
            //tracking = FindCameraPoseAlignDepthFloatToReconstruction();
            tracking = FindCameraPoseAlignPointClouds();

            if (FAILED(tracking) && tracking != E_NUI_FUSION_TRACKING_ERROR)
            {
                SetStatusMessage(L"Kinect Fusion FindCameraPose call failed.");
                goto FinishFrame;
            }
        }
    }
    else
    {
        if (m_bTrackingHasFailedPreviously)
        {
            WCHAR str[MAX_PATH];
            if (!m_paramsCurrent.m_bAutoFindCameraPoseWhenLost)
            {
                swprintf_s(str, ARRAYSIZE(str), L"Kinect Fusion camera tracking RECOVERED! Residual energy=%f", alignmentEnergy);
            }
            else
            {
                swprintf_s(str, ARRAYSIZE(str), L"Kinect Fusion camera tracking RECOVERED!");
            }
            SetStatusMessage(str);
        }

        m_worldToCameraTransform = calculatedCameraPose;
        SetTrackingSucceeded();
    }

    if (m_paramsCurrent.m_bAutoResetReconstructionWhenLost &&
        m_bTrackingFailed &&
        m_cLostFrameCounter >= cResetOnNumberOfLostFrames)
    {
        // Automatically Clear Volume and reset tracking if tracking fails
        hr = InternalResetReconstruction();

        if (SUCCEEDED(hr))
        {
            // Set bad tracking message
            SetStatusMessage(
                L"Kinect Fusion camera tracking failed, "
                L"automatically reset volume.");
        }
        else
        {
            SetStatusMessage(L"Kinect Fusion Reset Reconstruction call failed.");
            goto FinishFrame;
        }
    }

    ////////////////////////////////////////////////////////
    // Integrate Depth Data into volume

    // Don't integrate depth data into the volume if:
    // 1) tracking failed
    // 2) camera pose finder is off and we have paused capture
    // 3) camera pose finder is on and we are still under the m_cMinSuccessfulTrackingFramesForCameraPoseFinderAfterFailure
    //    number of successful frames count.
    bool integrateData = !m_bTrackingFailed && ((!cameraPoseFinderAvailable && !m_paramsCurrent.m_bPauseIntegration) 
        || (cameraPoseFinderAvailable && !(m_bTrackingHasFailedPreviously && m_cSuccessfulFrameCounter < m_paramsCurrent.m_cMinSuccessfulTrackingFramesForCameraPoseFinderAfterFailure)));

    if (integrateData)
    {
        if (cameraPoseFinderAvailable)
        {
            // If integration resumed, this will un-check the pause integration check box back on in the UI automatically
            m_bIntegrationResumed = true;
        }

        // Reset this flag as we are now integrating data again
        m_bTrackingHasFailedPreviously = false;

        if (integrateColor)
        {
            // Map the color frame to the depth - this fills m_pResampledColorImageDepthAligned
            MapColorToDepth();

            // Integrate the depth and color data into the volume from the calculated camera pose
            hr = m_pVolume->IntegrateFrame(
                    m_pDepthFloatImage,
                    m_pResampledColorImageDepthAligned,
                    m_paramsCurrent.m_cMaxIntegrationWeight,
                    NUI_FUSION_DEFAULT_COLOR_INTEGRATION_OF_ALL_ANGLES,
                    &m_worldToCameraTransform);

            m_frame.m_bColorCaptured = true;
        }
        else
        {
            // Integrate just the depth data into the volume from the calculated camera pose
            hr = m_pVolume->IntegrateFrame(
                    m_pDepthFloatImage,
                    nullptr,
                    m_paramsCurrent.m_cMaxIntegrationWeight,
                    NUI_FUSION_DEFAULT_COLOR_INTEGRATION_OF_ALL_ANGLES,
                    &m_worldToCameraTransform);
        }

        if (FAILED(hr))
        {
            SetStatusMessage(L"Kinect Fusion IntegrateFrame call failed.");
            goto FinishFrame;
        }
    }

    ////////////////////////////////////////////////////////
    // Check to see if we have time to raycast

    {
        double currentTime = m_timer.AbsoluteTime();

        // Is another frame already waiting?
        if (WaitForSingleObject(m_hNextDepthFrameEvent, 0) == WAIT_TIMEOUT)
        {
            // No: We should have enough time to raycast.
            raycastFrame = true;
        }
        else
        {
            // Yes: Raycast only if we've exceeded the render interval.
            double renderIntervalSeconds = (0.001 * cRenderIntervalMilliseconds);
            raycastFrame = (currentTime - m_fMostRecentRaycastTime > renderIntervalSeconds);
        }

        if (raycastFrame)
        {
            m_fMostRecentRaycastTime = currentTime;
        }
    }

    if (raycastFrame)
    {
        ////////////////////////////////////////////////////////
        // CalculatePointCloud

        // Raycast even if camera tracking failed, to enable us to visualize what is 
        // happening with the system
        hr = m_pVolume->CalculatePointCloud(
            m_pRaycastPointCloud,
            (m_paramsCurrent.m_bCaptureColor ? m_pCapturedSurfaceColor : nullptr), 
            &m_worldToCameraTransform);

        if (FAILED(hr))
        {
            SetStatusMessage(L"Kinect Fusion CalculatePointCloud call failed.");
            goto FinishFrame;
        }

        ////////////////////////////////////////////////////////
        // ShadePointCloud

        if (!m_paramsCurrent.m_bCaptureColor)
        {
            hr = NuiFusionShadePointCloud(
                m_pRaycastPointCloud,
                &m_worldToCameraTransform,
                &m_worldToBGRTransform,
                m_pShadedSurface,
                m_paramsCurrent.m_bDisplaySurfaceNormals ?  m_pShadedSurfaceNormals : nullptr);

            if (FAILED(hr))
            {
                SetStatusMessage(L"Kinect Fusion NuiFusionShadePointCloud call failed.");
                goto FinishFrame;
            }
        }
    }

    ////////////////////////////////////////////////////////
    // Update camera pose finder, adding key frames to the database

    if (m_paramsCurrent.m_bAutoFindCameraPoseWhenLost && !m_bTrackingHasFailedPreviously
        && m_cSuccessfulFrameCounter > m_paramsCurrent.m_cMinSuccessfulTrackingFramesForCameraPoseFinder
        && m_cFrameCounter % m_paramsCurrent.m_cCameraPoseFinderProcessFrameCalculationInterval == 0
        && colorSynchronized)
    {    
        hr  = UpdateCameraPoseFinder();

        if (FAILED(hr))
        {
            SetStatusMessage(L"Kinect Fusion UpdateCameraPoseFinder call failed.");
            goto FinishFrame;
        }
    }

FinishFrame:

    EnterCriticalSection(&m_lockFrame);

    if (cameraPoseFinderAvailable)
    {
        // Do not set false, as camera pose finder will toggle automatically depending on whether it has
        // regained tracking (re-localized) and is integrating again.
        m_frame.m_bIntegrationResumed = m_bIntegrationResumed;
    }
    else
    {
        m_frame.m_bIntegrationResumed = m_bIntegrationResumed;
        m_bIntegrationResumed = false;
    }

    ////////////////////////////////////////////////////////
    // Copy the images to their frame buffers

    if (depthAvailable)
    {
        StoreImageToFrameBuffer(m_pDepthFloatImage, m_frame.m_pDepthRGBX);
    }

    if (raycastFrame)
    {
        if (m_paramsCurrent.m_bCaptureColor)
        {
            StoreImageToFrameBuffer(m_pCapturedSurfaceColor, m_frame.m_pReconstructionRGBX);
        }
        else if (m_paramsCurrent.m_bDisplaySurfaceNormals)
        {
            StoreImageToFrameBuffer(m_pShadedSurfaceNormals, m_frame.m_pReconstructionRGBX);
        }
        else
        {
            StoreImageToFrameBuffer(m_pShadedSurface, m_frame.m_pReconstructionRGBX);
        }
    }

    // Display raycast depth image when in pose finding mode
    if (m_bTrackingFailed && cameraPoseFinderAvailable)
    {
        StoreImageToFrameBuffer(m_pRaycastDepthFloatImage, m_frame.m_pTrackingDataRGBX);
    }
    else
    {
        // Don't calculate the residual delta from reference frame every frame to reduce computation time
        if (m_bCalculateDeltaFrame )
        {
            if (!m_paramsCurrent.m_bAutoFindCameraPoseWhenLost)
            {
                // Color the float residuals from the AlignDepthFloatToReconstruction
                hr  = ColorResiduals(m_pFloatDeltaFromReference, m_pShadedDeltaFromReference);
            }

            if (SUCCEEDED(hr))
            {
                StoreImageToFrameBuffer(m_pShadedDeltaFromReference, m_frame.m_pTrackingDataRGBX);
            }
        }
    }

    ////////////////////////////////////////////////////////
    // Periodically Display Fps


    if (SUCCEEDED(hr))
    {
        // Update frame counter
        m_cFrameCounter++;

        // Display fps count approximately every cTimeDisplayInterval seconds
        double elapsed = m_timer.AbsoluteTime() - m_fFrameCounterStartTime;
        if (static_cast<int>(elapsed) >= cTimeDisplayInterval)
        {
            m_frame.m_fFramesPerSecond = 0;

            // Update status display
            if (!m_bTrackingFailed)
            {
                m_frame.m_fFramesPerSecond = static_cast<float>(m_cFrameCounter / elapsed);
            }

            m_cFrameCounter = 0;
            m_fFrameCounterStartTime = m_timer.AbsoluteTime();
        }
    }

    m_frame.SetStatusMessage(m_statusMessage);

    LeaveCriticalSection(&m_lockFrame);

    if (SUCCEEDED(hr))
    {
        m_exportFrameCounter++;
    }
    if ((m_exportFrameCounter >= m_nFrames)){
			INuiFusionColorMesh *mesh = nullptr;
			HRESULT hr2 = m_pVolume->CalculateMesh(1, &mesh);
			if (SUCCEEDED(hr2)){
				//FILE *meshFile = NULL;
                //errno_t err = fopen_s(&meshFile, "C:\\\\Users\\akratoc\\TanGeoMS\\output\\test1.obj", "wt");
                // Could not open file for writing - return
                //if (0 != err || NULL == meshFile)
                //{
                //	printf("NO FILE XXXX");fflush(stdout);
                //}
				int numVertices = mesh->VertexCount();
				const Vector3 *vertices = NULL;
				hr = mesh->GetVertices(&vertices);
                std::vector<Vector3> copyVector(vertices, vertices + numVertices);
                std::sort (copyVector.begin(), copyVector.end(), myLess);
                std::vector<Vector3>::const_iterator newit;
                newit = std::unique (copyVector.begin(), copyVector.end(), myEquals);

                // create lock file
                FILE *lockFile = NULL;
                std::string lockFileName = m_fileName + "lock";
                fopen_s(&lockFile, lockFileName.c_str(), "wt");
                fclose(lockFile);
                std::ofstream stream( m_fileName, std::ofstream::out);
                bool isopen = stream.is_open();
                for (std::vector<Vector3>::const_iterator it = copyVector.begin(); it != newit;++it){
					Vector3 vertex = *it;
					//vertex.y = -vertex.y;
					//vertex.z = -vertex.z;
                    //stream << "a" << std::endl;
                    stream << vertex.x << ' ' << -vertex.y << ' ' << -vertex.z << std::endl;

					//std::string vertexString = to_string(vertex.x) + " " + to_string(vertex.y) + " " + to_string(vertex.z) + "\n" ;
                    //fwrite(vertexString.c_str(), sizeof(char), vertexString.length(), meshFile);
				}
                    

                //for (std::unordered_set<std::string>::iterator it=unique_vertices.begin(); it!=unique_vertices.end(); ++it){
                //    fwrite((*it).c_str(), sizeof(char), (*it).length(), meshFile);
                //}
                stream.close();
				//fflush(meshFile);
				//fclose(meshFile);
                std::remove(lockFileName.c_str());
                m_exportFrameCounter = 0;
                InternalResetReconstruction();


			}
            SafeRelease(mesh);
		}
}

/// <summary>
/// Perform camera pose finding when tracking is lost using AlignPointClouds.
/// This is typically more successful than FindCameraPoseAlignDepthFloatToReconstruction.
/// </summary>
HRESULT KinectFusionProcessor::FindCameraPoseAlignPointClouds()
{
    HRESULT hr = S_OK;

    if (!IsCameraPoseFinderAvailable())
    {
        return E_FAIL;
    }

    bool resampled = false;

    hr = ProcessColorForCameraPoseFinder(resampled);

    if (FAILED(hr))
    {
        return hr;
    }

    // Start  kNN (k nearest neighbors) camera pose finding
    INuiFusionMatchCandidates *pMatchCandidates = nullptr;

    // Test the camera pose finder to see how similar the input images are to previously captured images.
    // This will return an error code if there are no matched frames in the camera pose finder database.
    hr = m_pCameraPoseFinder->FindCameraPose(
        m_pDepthFloatImage, 
        resampled ? m_pResampledColorImage : m_pColorImage,
        &pMatchCandidates);

    if (FAILED(hr) || nullptr == pMatchCandidates)
    {
        goto FinishFrame;
    }

    unsigned int cPoses = pMatchCandidates->MatchPoseCount();

    float minDistance = 1.0f;   // initialize to the maximum normalized distance
    hr = pMatchCandidates->CalculateMinimumDistance(&minDistance);

    if (FAILED(hr) || 0 == cPoses)
    {
        goto FinishFrame;
    }

    // Check the closest frame is similar enough to our database to re-localize
    // For frames that have a larger minimum distance, standard tracking will run
    // and if this fails, tracking will be considered lost.
    if (minDistance >= m_paramsCurrent.m_fCameraPoseFinderDistanceThresholdReject)
    {
        SetStatusMessage(L"FindCameraPose exited early as not good enough pose matches.");
        hr = E_NUI_NO_MATCH;
        goto FinishFrame;
    }

    // Get the actual matched poses
    const Matrix4 *pNeighbors = nullptr;
    hr = pMatchCandidates->GetMatchPoses(&pNeighbors);

    if (FAILED(hr))
    {
        goto FinishFrame;
    }

    ////////////////////////////////////////////////////////
    // Smooth depth image

    hr = m_pVolume->SmoothDepthFloatFrame(
        m_pDepthFloatImage, 
        m_pSmoothDepthFloatImage, 
        m_paramsCurrent.m_cSmoothingKernelWidth, 
        m_paramsCurrent.m_fSmoothingDistanceThreshold); // ON GPU

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion SmoothDepth call failed.");
        goto FinishFrame;
    }

    ////////////////////////////////////////////////////////
    // Calculate Point Cloud from smoothed input Depth Image

    hr = NuiFusionDepthFloatFrameToPointCloud(
        m_pSmoothDepthFloatImage,
        m_pDepthPointCloud);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion NuiFusionDepthFloatFrameToPointCloud call failed.");
        goto FinishFrame;
    }

    HRESULT tracking = S_OK;
    FLOAT alignmentEnergy = 0;

    unsigned short relocIterationCount = NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT;

    double smallestEnergy = DBL_MAX;
    int smallestEnergyNeighborIndex = -1;

    int bestNeighborIndex = -1;
    Matrix4 bestNeighborCameraPose;
    SetIdentityMatrix(bestNeighborCameraPose);
    // Exclude very tiny alignment energy case which is unlikely to happen in reality - this is more likely a tracking error
    double bestNeighborAlignmentEnergy = m_paramsCurrent.m_fMaxAlignPointCloudsEnergyForSuccess;

    // Run alignment with best matched poses (i.e. k nearest neighbors (kNN))
    unsigned int maxTests = min(m_paramsCurrent.m_cMaxCameraPoseFinderPoseTests, cPoses);

    for (unsigned int n = 0; n < maxTests; n++)
    {
        ////////////////////////////////////////////////////////
        // Call AlignPointClouds

        Matrix4 poseProposal = pNeighbors[n];

        // Get the saved pose view by raycasting the volume
        hr = m_pVolume->CalculatePointCloud(m_pRaycastPointCloud, nullptr, &poseProposal);

        tracking = m_pVolume->AlignPointClouds(
            m_pRaycastPointCloud,
            m_pDepthPointCloud,
            relocIterationCount,
            nullptr,
            &alignmentEnergy,
            &poseProposal); 


        if (SUCCEEDED(tracking) && alignmentEnergy < bestNeighborAlignmentEnergy  && alignmentEnergy > m_paramsCurrent.m_fMinAlignPointCloudsEnergyForSuccess)
        {
            bestNeighborAlignmentEnergy = alignmentEnergy;
            bestNeighborIndex = n;

            // This is after tracking succeeds, so should be a more accurate pose to store...
            bestNeighborCameraPose = poseProposal; 
        }

        // Find smallest energy neighbor independent of tracking success
        if (alignmentEnergy < smallestEnergy)
        {
            smallestEnergy = alignmentEnergy;
            smallestEnergyNeighborIndex = n;
        }
    }

    // Use the neighbor with the smallest residual alignment energy
    // At the cost of additional processing we could also use kNN+Mean camera pose finding here
    // by calculating the mean pose of the best n matched poses and also testing this to see if the 
    // residual alignment energy is less than with kNN.
    if (bestNeighborIndex > -1)
    {
        m_worldToCameraTransform = bestNeighborCameraPose;

        // Get the saved pose view by raycasting the volume
        hr = m_pVolume->CalculatePointCloud(m_pRaycastPointCloud, nullptr, &m_worldToCameraTransform);

        if (FAILED(hr))
        {
            goto FinishFrame;
        }

        // Tracking succeeded!
        hr = S_OK;

        SetTrackingSucceeded();

        // Run a single iteration of AlignPointClouds to get the deltas frame
        hr = m_pVolume->AlignPointClouds(
            m_pRaycastPointCloud,
            m_pDepthPointCloud,
            1,
            m_pShadedDeltaFromReference,
            &alignmentEnergy,
            &bestNeighborCameraPose); 

        if (SUCCEEDED(hr))
        {
            StoreImageToFrameBuffer(m_pShadedDeltaFromReference, m_frame.m_pTrackingDataRGBX);
        }

        // Stop the residual image being displayed as we have stored our own
        m_bCalculateDeltaFrame = false;

        WCHAR str[MAX_PATH];
        swprintf_s(str, ARRAYSIZE(str), L"Camera Pose Finder SUCCESS! Residual energy=%f, %d frames stored, minimum distance=%f, best match index=%d", bestNeighborAlignmentEnergy, cPoses, minDistance, bestNeighborIndex);
        SetStatusMessage(str);
    }
    else
    {        
        m_worldToCameraTransform = pNeighbors[smallestEnergyNeighborIndex];

        // Get the smallest energy view by raycasting the volume
        hr = m_pVolume->CalculatePointCloud(m_pRaycastPointCloud, nullptr, &m_worldToCameraTransform);

        if (FAILED(hr))
        {
            goto FinishFrame;
        }

        // Camera pose finding failed - return the tracking failed error code
        hr = E_NUI_FUSION_TRACKING_ERROR;

        // Tracking Failed will be set again on the next iteration in ProcessDepth
        WCHAR str[MAX_PATH];
        swprintf_s(str, ARRAYSIZE(str), L"Camera Pose Finder FAILED! Residual energy=%f, %d frames stored, minimum distance=%f, best match index=%d", smallestEnergy, cPoses, minDistance, smallestEnergyNeighborIndex);
        SetStatusMessage(str);
    }

FinishFrame:

    SafeRelease(pMatchCandidates);

    return hr;
}


/// <summary>
/// Perform camera pose finding when tracking is lost using AlignDepthFloatToReconstruction.
/// </summary>
HRESULT KinectFusionProcessor::FindCameraPoseAlignDepthFloatToReconstruction()
{
    HRESULT hr = S_OK;

    if (!IsCameraPoseFinderAvailable())
    {
        return E_FAIL;
    }

    bool resampled = false;

    hr = ProcessColorForCameraPoseFinder(resampled);

    if (FAILED(hr))
    {
        return hr;
    }

    // Start  kNN (k nearest neighbors) camera pose finding
    INuiFusionMatchCandidates *pMatchCandidates = nullptr;

    // Test the camera pose finder to see how similar the input images are to previously captured images.
    // This will return an error code if there are no matched frames in the camera pose finder database.
    hr = m_pCameraPoseFinder->FindCameraPose(
        m_pDepthFloatImage, 
        resampled ? m_pResampledColorImage : m_pColorImage,
        &pMatchCandidates);

    if (FAILED(hr) || nullptr == pMatchCandidates)
    {
        goto FinishFrame;
    }

    unsigned int cPoses = pMatchCandidates->MatchPoseCount();

    float minDistance = 1.0f;   // initialize to the maximum normalized distance
    hr = pMatchCandidates->CalculateMinimumDistance(&minDistance);

    if (FAILED(hr) || 0 == cPoses)
    {
        goto FinishFrame;
    }

    // Check the closest frame is similar enough to our database to re-localize
    // For frames that have a larger minimum distance, standard tracking will run
    // and if this fails, tracking will be considered lost.
    if (minDistance >= m_paramsCurrent.m_fCameraPoseFinderDistanceThresholdReject)
    {
        SetStatusMessage(L"FindCameraPose exited early as not good enough pose matches.");
        hr = E_NUI_NO_MATCH;
        goto FinishFrame;
    }

    // Get the actual matched poses
    const Matrix4 *pNeighbors = nullptr;
    hr = pMatchCandidates->GetMatchPoses(&pNeighbors);

    if (FAILED(hr))
    {
        goto FinishFrame;
    }

    HRESULT tracking = S_OK;
    FLOAT alignmentEnergy = 0;

    unsigned short relocIterationCount = NUI_FUSION_DEFAULT_ALIGN_ITERATION_COUNT;

    double smallestEnergy = DBL_MAX;
    int smallestEnergyNeighborIndex = -1;

    int bestNeighborIndex = -1;
    Matrix4 bestNeighborCameraPose;
    SetIdentityMatrix(bestNeighborCameraPose);
    // Exclude very tiny alignment energy case which is unlikely to happen in reality - this is more likely a tracking error
    double bestNeighborAlignmentEnergy = m_paramsCurrent.m_fMaxAlignToReconstructionEnergyForSuccess;

    // Run alignment with best matched poses (i.e. k nearest neighbors (kNN))
    unsigned int maxTests = min(m_paramsCurrent.m_cMaxCameraPoseFinderPoseTests, cPoses);

    for (unsigned int n = 0; n < maxTests; n++)
    {
        ////////////////////////////////////////////////////////
        // Call AlignDepthFloatToReconstruction

        // Run the camera tracking algorithm with the volume
        // this uses the raycast frame and pose to find a valid camera pose by matching the depth against the volume
        hr = SetReferenceFrame(pNeighbors[n]);

        if (FAILED(hr))
        {
            continue;
        }

        tracking = m_pVolume->AlignDepthFloatToReconstruction( 
            m_pDepthFloatImage,
            relocIterationCount,
            m_pFloatDeltaFromReference,
            &alignmentEnergy,
            &(pNeighbors[n]));

        bool relocSuccess = SUCCEEDED(tracking) && alignmentEnergy < bestNeighborAlignmentEnergy && alignmentEnergy > m_paramsCurrent.m_fMinAlignToReconstructionEnergyForSuccess;
        
        if (relocSuccess)
        {
            if (SUCCEEDED(tracking))
            {
                bestNeighborAlignmentEnergy = alignmentEnergy;
                bestNeighborIndex = n;

                // This is after tracking succeeds, so should be a more accurate pose to store...
                m_pVolume->GetCurrentWorldToCameraTransform(&bestNeighborCameraPose); 
            }
        }

        // Find smallest energy neighbor independent of tracking success
        if (alignmentEnergy < smallestEnergy)
        {
            smallestEnergy = alignmentEnergy;
            smallestEnergyNeighborIndex = n;
        }
    }

    // Use the neighbor with the smallest residual alignment energy
    // At the cost of additional processing we could also use kNN+Mean camera pose finding here
    // by calculating the mean pose of the best n matched poses and also testing this to see if the 
    // residual alignment energy is less than with kNN.
    if (bestNeighborIndex > -1)
    {       
        m_worldToCameraTransform = bestNeighborCameraPose;
        hr = SetReferenceFrame(m_worldToCameraTransform);

        if (FAILED(hr))
        {
            goto FinishFrame;
        }

        // Tracking succeeded!
        hr = S_OK;

        SetTrackingSucceeded();

        // Force the residual image to be displayed
        m_bCalculateDeltaFrame = true;

        WCHAR str[MAX_PATH];
        swprintf_s(str, ARRAYSIZE(str), L"Camera Pose Finder SUCCESS! Residual energy=%f, %d frames stored, minimum distance=%f, best match index=%d", bestNeighborAlignmentEnergy, cPoses, minDistance, bestNeighborIndex);
        SetStatusMessage(str);
    }
    else
    {        
        m_worldToCameraTransform = pNeighbors[smallestEnergyNeighborIndex];
        hr = SetReferenceFrame(m_worldToCameraTransform);

        if (FAILED(hr))
        {
            goto FinishFrame;
        }

        // Camera pose finding failed - return the tracking failed error code
        hr = E_NUI_FUSION_TRACKING_ERROR;

        // Tracking Failed will be set again on the next iteration in ProcessDepth
        WCHAR str[MAX_PATH];
        swprintf_s(str, ARRAYSIZE(str), L"Camera Pose Finder FAILED! Residual energy=%f, %d frames stored, minimum distance=%f, best match index=%d", smallestEnergy, cPoses, minDistance, smallestEnergyNeighborIndex);
        SetStatusMessage(str);
    }

FinishFrame:

    SafeRelease(pMatchCandidates);

    return hr;
}

/// <summary>
/// Performs raycasting for given pose and sets the tracking reference frame
/// </summary>
/// <param name="worldToCamera">The reference camera pose.</param>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::SetReferenceFrame(const Matrix4 &worldToCamera)
{
    HRESULT hr = S_OK;

    // Raycast to get the predicted previous frame to align against in the next frame
    hr = m_pVolume->CalculatePointCloudAndDepth(
        m_pRaycastPointCloud, 
        m_pRaycastDepthFloatImage, 
        nullptr, 
        &worldToCamera);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion CalculatePointCloud call failed.");
        return hr;
    }

    // Set this frame as a reference for AlignDepthFloatToReconstruction
    hr =  m_pVolume->SetAlignDepthFloatToReconstructionReferenceFrame(m_pRaycastDepthFloatImage);

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion SetAlignDepthFloatToReconstructionReferenceFrame call failed.");
        return hr;
    }

    return hr;
}

/// <summary>
/// Update the status on tracking failure.
/// </summary>
void KinectFusionProcessor::SetTrackingFailed()
{
    m_cLostFrameCounter++;
    m_cSuccessfulFrameCounter = 0;
    m_bTrackingFailed = true;
    m_bTrackingHasFailedPreviously = true;

    m_bIntegrationResumed = false;
}

/// <summary>
/// Update the status when tracking succeeds.
/// </summary>
void KinectFusionProcessor::SetTrackingSucceeded()
{
    m_cLostFrameCounter = 0;
    m_cSuccessfulFrameCounter++;
    m_bTrackingFailed = false;
}

/// <summary>
/// Reset the tracking flags
/// </summary>
void KinectFusionProcessor::ResetTracking()
{
    m_bTrackingFailed = false;
    m_bTrackingHasFailedPreviously = false;

    m_cLostFrameCounter = 0;
    m_cSuccessfulFrameCounter = 0;

    // Reset pause and signal that the integration resumed
    m_paramsCurrent.m_bPauseIntegration = false;
    m_paramsNext.m_bPauseIntegration = false;
    m_bIntegrationResumed = true;
    m_frame.m_bIntegrationResumed = true;
    m_frame.m_bColorCaptured = false;

    if (nullptr != m_pCameraPoseFinder)
    {
        m_pCameraPoseFinder->ResetCameraPoseFinder();
    }
}

/// <summary>
/// Process the color image for the camera pose finder.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::ProcessColorForCameraPoseFinder(bool &resampled)
{
    HRESULT hr = S_OK;

    // If color and depth are different resolutions we first we re-sample the color frame using nearest neighbor
    // before passing to the CameraPoseFinder
    if (m_paramsCurrent.m_cDepthImagePixels != m_paramsCurrent.m_cColorImagePixels)
    {
        if (m_pColorImage->width > m_pResampledColorImage->width)
        {
            // Down-sample
            unsigned int factor = m_pColorImage->width / m_pResampledColorImage->width;
            hr = DownsampleFrameNearestNeighbor(m_pColorImage, m_pResampledColorImage, factor);

            if (FAILED(hr))
            {
                SetStatusMessage(L"Kinect Fusion DownsampleFrameNearestNeighbor call failed.");
                return hr;
            }
        }
        else
        {
            // Up-sample
            unsigned int factor = m_pResampledColorImage->width / m_pColorImage->width;
            hr = UpsampleFrameNearestNeighbor(m_pColorImage, m_pResampledColorImage, factor);

            if (FAILED(hr))
            {
                SetStatusMessage(L"Kinect Fusion UpsampleFrameNearestNeighbor call failed.");
                return hr;
            }
        }

        resampled = true;
    }
    else
    {
        resampled = false;
    }

    return hr;
}

/// <summary>
/// Update the camera pose finder data.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::UpdateCameraPoseFinder()
{
    AssertOwnThread();

    HRESULT hr = S_OK;

    if (nullptr == m_pDepthFloatImage || nullptr == m_pColorImage  
        || nullptr == m_pResampledColorImage || nullptr == m_pCameraPoseFinder)
    {
        return E_FAIL;
    }

    bool resampled = false;

    hr = ProcessColorForCameraPoseFinder(resampled);

    if (FAILED(hr))
    {
        return hr;
    }

    BOOL poseHistoryTrimmed = FALSE;
    BOOL addedPose = FALSE;

    // This function will add the pose to the camera pose finding database when the input frame's minimum
    // distance to the existing database is equal to or above m_fDistanceThresholdAccept (i.e. indicating 
    // that the input has become dis-similar to the existing database and a new frame should be captured).
    // Note that the color and depth frames must be the same size, however, the horizontal mirroring
    // setting does not have to be consistent between depth and color. It does have to be consistent
    // between camera pose finder database creation and calling FindCameraPose though, hence we always
    // reset both the reconstruction and database when changing the mirror depth setting.
    hr = m_pCameraPoseFinder->ProcessFrame(
        m_pDepthFloatImage, 
        resampled ? m_pResampledColorImage : m_pColorImage,
        &m_worldToCameraTransform, 
        m_paramsCurrent.m_fCameraPoseFinderDistanceThresholdAccept, 
        &addedPose, 
        &poseHistoryTrimmed);

    if (TRUE == addedPose)
    {
        WCHAR str[MAX_PATH];
        swprintf_s(str, ARRAYSIZE(str), L"Camera Pose Finder Added Frame! %d frames stored, minimum distance>=%f\n", m_pCameraPoseFinder->GetStoredPoseCount(), m_paramsCurrent.m_fCameraPoseFinderDistanceThresholdAccept);
        SetStatusMessage(str);
    }

    if (TRUE == poseHistoryTrimmed)
    {
        SetStatusMessage(L"Kinect Fusion Camera Pose Finder pose history is full, overwritten oldest pose to store current pose.");
    }

    if (FAILED(hr))
    {
        SetStatusMessage(L"Kinect Fusion Camera Pose Finder Process Frame call failed.");
    }

    return hr;
}

/// <summary>
/// Store a Kinect Fusion image to a frame buffer.
/// Accepts Depth Float, and Color image types.
/// </summary>
/// <param name="imageFrame">The image frame to store.</param>
/// <param name="buffer">The frame buffer.</param>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::StoreImageToFrameBuffer(
    const NUI_FUSION_IMAGE_FRAME* imageFrame,
    BYTE* buffer)
{
    AssertOwnThread();

    HRESULT hr = S_OK;

    if (nullptr == imageFrame || nullptr == imageFrame->pFrameTexture || nullptr == buffer)
    {
        return E_INVALIDARG;
    }

    if (NUI_FUSION_IMAGE_TYPE_COLOR != imageFrame->imageType &&
        NUI_FUSION_IMAGE_TYPE_FLOAT != imageFrame->imageType)
    {
        return E_INVALIDARG;
    }

    if (0 == imageFrame->width || 0 == imageFrame->height)
    {
        return E_NOINTERFACE;
    }

    INuiFrameTexture *imageFrameTexture = imageFrame->pFrameTexture;
    NUI_LOCKED_RECT LockedRect;

    // Lock the frame data so the Kinect knows not to modify it while we're reading it
    imageFrameTexture->LockRect(0, &LockedRect, nullptr, 0);

    // Make sure we've received valid data
    if (LockedRect.Pitch != 0)
    {
        // Convert from floating point depth if required
        if (NUI_FUSION_IMAGE_TYPE_FLOAT == imageFrame->imageType)
        {
            // Depth ranges set here for better visualization, and map to black at 0 and white at 4m
            const FLOAT range = 4.0f;
            const FLOAT oneOverRange = (1.0f / range) * 256.0f;
            const FLOAT minRange = 0.0f;

            const float *pFloatBuffer = reinterpret_cast<float *>(LockedRect.pBits);

            Concurrency::parallel_for(0u, imageFrame->height, [&](unsigned int y)
            {
                unsigned int* pColorRow = reinterpret_cast<unsigned int*>(reinterpret_cast<unsigned char*>(buffer) + (y * LockedRect.Pitch));
                const float* pFloatRow = reinterpret_cast<const float*>(reinterpret_cast<const unsigned char*>(pFloatBuffer) + (y * LockedRect.Pitch));

                for (unsigned int x = 0; x < imageFrame->width; ++x)
                {
                    float depth = pFloatRow[x];

                    // Note: Using conditionals in this loop could degrade performance.
                    // Consider using a lookup table instead when writing production code.
                    BYTE intensity = (depth >= minRange) ?
                        static_cast<BYTE>( (int)((depth - minRange) * oneOverRange) % 256 ) :
                        0; // % 256 to enable it to wrap around after the max range

                    pColorRow[x] = (255 << 24) | (intensity << 16) | (intensity << 8 ) | intensity;
                }
            });
        }
        else	// already in 4 bytes per int (RGBA/BGRA) format
        {
            const size_t destPixelCount =
                m_paramsCurrent.m_cDepthWidth * m_paramsCurrent.m_cDepthHeight;

            BYTE * pBuffer = (BYTE *)LockedRect.pBits;

            // Draw the data with Direct2D
            memcpy_s(
                buffer,
                destPixelCount * KinectFusionParams::BytesPerPixel,
                pBuffer,
                imageFrame->width * imageFrame->height * KinectFusionParams::BytesPerPixel);
        }
    }
    else
    {
        return E_NOINTERFACE;
    }

    // We're done with the texture so unlock it
    imageFrameTexture->UnlockRect(0);

    return hr;
}

/// <summary>
/// Reset the reconstruction camera pose and clear the volume on the next frame.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::ResetReconstruction()
{
    AssertOtherThread();

    EnterCriticalSection(&m_lockParams);
    m_bResetReconstruction = true;
    LeaveCriticalSection(&m_lockParams);

    return S_OK;
}

/// <summary>
/// Reset the reconstruction camera pose and clear the volume.
/// </summary>
/// <returns>S_OK on success, otherwise failure code</returns>
HRESULT KinectFusionProcessor::InternalResetReconstruction()
{
    AssertOwnThread();

    if (nullptr == m_pVolume)
    {
        return E_FAIL;
    }

    HRESULT hr = S_OK;

    SetIdentityMatrix(m_worldToCameraTransform);

    // Translate the world origin away from the reconstruction volume location by an amount equal
    // to the minimum depth threshold. This ensures that some depth signal falls inside the volume.
    // If set false, the default world origin is set to the center of the front face of the 
    // volume, which has the effect of locating the volume directly in front of the initial camera
    // position with the +Z axis into the volume along the initial camera direction of view.
    if (m_paramsCurrent.m_bTranslateResetPoseByMinDepthThreshold)
    {
        Matrix4 worldToVolumeTransform = m_defaultWorldToVolumeTransform;

        // Translate the volume in the Z axis by the minDepthThreshold distance
        float minDist = (m_paramsCurrent.m_fMinDepthThreshold < m_paramsCurrent.m_fMaxDepthThreshold) ? m_paramsCurrent.m_fMinDepthThreshold : m_paramsCurrent.m_fMaxDepthThreshold;
        worldToVolumeTransform.M43 -= (minDist * m_paramsCurrent.m_reconstructionParams.voxelsPerMeter);

        hr = m_pVolume->ResetReconstruction(&m_worldToCameraTransform, &worldToVolumeTransform);
    }
    else
    {
        hr = m_pVolume->ResetReconstruction(&m_worldToCameraTransform, nullptr);
    }

    m_cFrameCounter = 0;
    m_fFrameCounterStartTime = m_timer.AbsoluteTime();

    EnterCriticalSection(&m_lockFrame);
    m_frame.m_fFramesPerSecond = 0;
    LeaveCriticalSection(&m_lockFrame);

    if (SUCCEEDED(hr))
    {
        ResetTracking();
    }

    return hr;
}

/// <summary>
/// Calculate a mesh for the current volume
/// </summary>
/// <param name="ppMesh">returns the new mesh</param>
HRESULT KinectFusionProcessor::CalculateMesh(INuiFusionColorMesh** ppMesh)
{
    AssertOtherThread();

    EnterCriticalSection(&m_lockVolume);

    HRESULT hr = E_FAIL;

    if (m_pVolume != nullptr)
    {
        hr = m_pVolume->CalculateMesh(1, ppMesh);

        // Set the frame counter to 0 to prevent a reset reconstruction call due to large frame 
        // timestamp change after meshing. Also reset frame time for fps counter.
        m_cFrameCounter = 0;
        m_fFrameCounterStartTime =  m_timer.AbsoluteTime();
    }

    LeaveCriticalSection(&m_lockVolume);

    return hr;
}

/// <summary>
/// Set the status bar message
/// </summary>
/// <param name="szMessage">message to display</param>
void KinectFusionProcessor::SetStatusMessage(WCHAR * szMessage)
{
    AssertOwnThread();

    StringCchCopy(m_statusMessage, ARRAYSIZE(m_statusMessage), szMessage);
}

/// <summary>
/// Notifies the UI window that a new frame is ready
/// </summary>
void KinectFusionProcessor::NotifyFrameReady()
{
    AssertOwnThread();

    if (m_hWnd != nullptr && m_msgFrameReady != WM_NULL)
    {
        PostMessage(m_hWnd, m_msgFrameReady, 0, 0);
    }
}

/// <summary>
/// Notifies the UI window to update, even though there is no new frame data
/// </summary>
void KinectFusionProcessor::NotifyEmptyFrame()
{
    AssertOwnThread();

    EnterCriticalSection(&m_lockFrame);
    m_frame.m_fFramesPerSecond = 0;
    m_frame.SetStatusMessage(m_statusMessage);
    LeaveCriticalSection(&m_lockFrame);

    NotifyFrameReady();
}

