//------------------------------------------------------------------------------
// <copyright file="KinectFusionProcessorFrame.h" company="Microsoft">
// 	 
//	 Copyright 2013 Microsoft Corporation 
// 	 
//	Licensed under the Apache License, Version 2.0 (the "License"); 
//	you may not use this file except in compliance with the License.
//	You may obtain a copy of the License at
// 	 
//		 http://www.apache.org/licenses/LICENSE-2.0 
// 	 
//	Unless required by applicable law or agreed to in writing, software 
//	distributed under the License is distributed on an "AS IS" BASIS,
//	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
//	See the License for the specific language governing permissions and 
//	limitations under the License. 
// 	 
// </copyright>
//------------------------------------------------------------------------------

#pragma once

/// <summary>
/// Contains the per-frame data produced by KinectFusionProcessor.
/// </summary>
struct KinectFusionProcessorFrame
{
    static const int StatusMessageMaxLen = MAX_PATH*2;

public:

    /// <summary>
    /// Constructor.
    /// </summary>
    KinectFusionProcessorFrame();

    /// <summary>
    /// Destructor.
    /// </summary>
    ~KinectFusionProcessorFrame();

    /// <summary>
    /// Initializes each of the frame buffers to the given image size.
    /// </summary>
    /// <param name="cImageSize">Number of pixels to allocate in each frame buffer.</param>
    HRESULT Initialize(int cImageSize);

    /// <summary>
    /// Sets the status message for the frame.
    /// </summary>
    /// <param name="szMessage">The status message.</param>
    void SetStatusMessage(const WCHAR* szMessage);

    // Indicates whether integration spontaneously resumed (due to a reset)
    bool m_bIntegrationResumed;

    // Frame buffer data
    BYTE* m_pReconstructionRGBX;
    BYTE* m_pDepthRGBX;
    BYTE* m_pTrackingDataRGBX;

    // Count of bytes in each frame buffer
    unsigned long m_cbImageSize;

    // Status message for the current frame
    WCHAR m_statusMessage[StatusMessageMaxLen];

    // Frame rate (in Hz)
    float m_fFramesPerSecond;

    // Set true when color has been captured, which enables us to save color into a .PLY mesh
    bool m_bColorCaptured;

    // As we now create a color volume in addition to the depth volume, the memory requirement
    // for a given volume size has doubled. Here we return the total dedicated memory available.
    unsigned int m_deviceMemory;

private:
    /// <summary>
    /// Frees the frame buffers.
    /// </summary>
    void FreeBuffers();
};
